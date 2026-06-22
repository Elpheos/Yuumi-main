# members/tests_ai_agent.py
#
# Batterie de tests pour l'agent IA Yuumi apres les 5 ameliorations.
#
# Lancer :  python manage.py test members.tests_ai_agent -v 2
#
# Principe : base de test jetable + fixtures isolees. Les 3 appels LLM
# (understand_intent / extract_search_params / recommend_stores) sont MOCKES
# pour tester toute la plomberie de facon deterministe, SANS appeler Mistral
# et SANS consommer de quota. La couche recherche (ORM) tourne POUR DE VRAI
# contre les fixtures. Un test verifie aussi le cablage du prompt cote client.

import json
from datetime import time
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.contrib.auth import get_user_model

from members.models import Store, Category, SuperCategory, ProductFamily, Product, Click
from members.views import ai_search_agent

from members.ai_agent.search import (
    find_matching_stores,
    find_stores_by_product,
    find_stores_by_description,
    combine_store_querysets,
)
from members.ai_agent.client import needs_web_search


VILLE = "Annecy"
DEPT = "Haute-Savoie"

# Horaires "ouvert tout le temps" (tous les jours 00:00 -> 23:59), pour qu'un
# commerce ressorte comme ouvert quelle que soit l'heure d'execution du test.
_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
OPEN_ALWAYS = {}
for _j in _JOURS:
    OPEN_ALWAYS[f"{_j}_matin_ouverture"] = time(0, 0)
    OPEN_ALWAYS[f"{_j}_matin_fermeture"] = time(23, 59)


def make_category(name):
    sc, _ = SuperCategory.objects.get_or_create(
        name="Commerces", defaults={"slug": "commerces"}
    )
    cat = Category.objects.create(name=name, super_categorie=sc)
    return cat  # slug auto = slugify(name)


def make_store(nom, cat, desc="Description neutre.", clicks=0, open_now=False):
    extra = dict(OPEN_ALWAYS) if open_now else {}
    store = Store.objects.create(
        nom=nom,
        ville=VILLE,
        ville_precise=VILLE,
        departement=DEPT,
        descriptionpetite=desc,
        addressemaps="1 rue du Test",
        categorie=cat,
        latitude=45.9,   # fixe -> pas de thread de geocodage au save()
        longitude=6.13,
        **extra,
    )
    for _ in range(clicks):
        Click.objects.create(store=store, type_click="site")
    return store


def add_product(store, product_nom, family_nom="Famille generique"):
    fam = ProductFamily.objects.create(store=store, nom=family_nom)
    Product.objects.create(family=fam, nom=product_nom)
    return fam


# =====================================================================
#  1. COUCHE RECHERCHE (ORM reel)
# =====================================================================
class SearchLayerTests(TestCase):
    def setUp(self):
        self.cat_epicerie = make_category("Épicerie fine")
        self.cat_charcuterie = make_category("Charcuterie")

    def test_product_match_sur_nom_produit(self):
        s = make_store("Charcuterie Dupont", self.cat_charcuterie)
        add_product(s, "Foie gras maison")
        res = list(find_stores_by_product(["foie gras"], DEPT, VILLE))
        self.assertIn(s, res)

    def test_product_match_sur_nom_famille(self):
        # Le nom du PRODUIT ne contient pas "foie gras", mais la FAMILLE oui.
        # C'est l'elargissement du match (point 1).
        s = make_store("Maison Martin", self.cat_charcuterie)
        add_product(s, "Terrine du chef", family_nom="Foie gras & terrines")
        res = list(find_stores_by_product(["foie gras"], DEPT, VILLE))
        self.assertIn(s, res)

    def test_description_match(self):
        s = make_store(
            "Épicerie Lefevre", self.cat_epicerie,
            desc="Épicerie fine proposant foie gras, vins et fromages.",
        )
        res = list(find_stores_by_description(["foie gras"], DEPT, VILLE))
        self.assertIn(s, res)
        # Et PAS via le catalogue (aucun Product).
        self.assertNotIn(s, list(find_stores_by_product(["foie gras"], DEPT, VILLE)))

    def test_tri_par_clics(self):
        a = make_store("AAA Commerce", self.cat_epicerie, clicks=0)
        b = make_store("ZZZ Commerce", self.cat_epicerie, clicks=5)
        res = list(find_matching_stores([self.cat_epicerie.slug], DEPT, VILLE))
        # Malgre l'ordre alphabetique (AAA avant ZZZ), ZZZ (5 clics) passe 1er.
        self.assertEqual(res[0], b)
        self.assertEqual(res[1], a)

    def test_open_now_filtre_en_sql(self):
        ouvert = make_store("Ouvert", self.cat_epicerie, open_now=True)
        ferme = make_store("Ferme", self.cat_epicerie, open_now=False)
        sans_filtre = list(find_matching_stores([self.cat_epicerie.slug], DEPT, VILLE))
        self.assertIn(ouvert, sans_filtre)
        self.assertIn(ferme, sans_filtre)
        avec_filtre = list(
            find_matching_stores([self.cat_epicerie.slug], DEPT, VILLE, ouvert_maintenant=True)
        )
        self.assertIn(ouvert, avec_filtre)
        self.assertNotIn(ferme, avec_filtre)

    def test_combine_dedup_cap_et_ordre(self):
        s1 = make_store("S1", self.cat_epicerie)
        s2 = make_store("S2", self.cat_charcuterie)
        add_product(s2, "Foie gras maison")
        qs_prod = find_stores_by_product(["foie gras"], DEPT, VILLE)   # [s2]
        qs_cat = find_matching_stores([self.cat_epicerie.slug], DEPT, VILLE)  # [s1]
        # Produit d'abord -> s2 avant s1, et pas de doublon.
        combined = combine_store_querysets(qs_prod, qs_cat)
        self.assertEqual([x.id for x in combined], [s2.id, s1.id])
        # Plafond respecte.
        capped = combine_store_querysets(qs_prod, qs_cat, limit=1)
        self.assertEqual(len(capped), 1)


# =====================================================================
#  2. HEURISTIQUE WEB
# =====================================================================
class WebHeuristicTests(TestCase):
    def test_pas_de_web_pour_produit_simple(self):
        for q in ["je veux du foie gras", "un fleuriste", "cadeau pour ma mere"]:
            self.assertFalse(needs_web_search(q), q)

    def test_web_pour_signaux_externes(self):
        for q in [
            "un resto sympa vu la météo",
            "qu'est-ce qui est tendance en ce moment",
            "un évènement ce week-end",
        ]:
            self.assertTrue(needs_web_search(q), q)


# =====================================================================
#  3. ORCHESTRATION DE LA VUE (LLM mockes, recherche reelle)
# =====================================================================
class ViewOrchestrationTests(TestCase):
    @staticmethod
    def _fake_recommend(user_query, stores, ids_par_produit=None,
                        produit_sans_match_confirme=False, ouvert_maintenant=False):
        ids_par_produit = ids_par_produit or set()
        return {
            "intention": "produit_precis",
            "message": "ok",
            "pistes": [{
                "angle": "Notre selection",
                "resultats": [
                    {
                        "id": s.id,
                        "confiance": "confirme" if s.id in ids_par_produit else "deduit",
                        "justification": "x",
                    }
                    for s in stores
                ],
            }],
            "aucun_resultat": not stores,
        }

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(username="prem", password="x")

        self.cat_epicerie = make_category("Épicerie fine")
        self.cat_charcuterie = make_category("Charcuterie")
        self.cat_fleuriste = make_category("Fleuriste")

        def _p(target, **kw):
            p = patch(target, **kw)
            m = p.start()
            self.addCleanup(p.stop)
            return m

        _p("members.views.can_use_ai_agent", return_value=True)
        self.m_register = _p("members.views.register_ai_usage")
        self.m_understand = _p("members.views.understand_intent", return_value="intention libre")
        self.m_extract = _p("members.views.extract_search_params")
        self.m_recommend = _p("members.views.recommend_stores", side_effect=self._fake_recommend)

    def _post(self, query):
        req = self.factory.post(
            "/agent-ia/", {"query": query, "departement": DEPT, "ville": VILLE}
        )
        req.user = self.user
        resp = ai_search_agent(req)
        return resp, json.loads(resp.content)

    def _params(self, **kw):
        base = {
            "categories": [], "idees_produits": [],
            "hors_sujet": False, "categorie_absente": False,
            "besoin_clarification": False, "questions_clarification": [],
            "ouvert_maintenant": False,
        }
        base.update(kw)
        return base

    # ---- Scenario "Famille Mary" : produit precis, AUCUN match catalogue/desc
    def test_foie_gras_sans_match_utilise_filet_categorie_et_flag(self):
        honey = make_store(
            "Famille Mary", self.cat_epicerie,
            desc="Specialiste des produits de la ruche, epicerie fine.",
        )  # pas de produit, description ne mentionne PAS foie gras
        self.m_extract.return_value = self._params(
            categories=[self.cat_epicerie.slug], idees_produits=["foie gras"]
        )
        resp, data = self._post("je veux du foie gras")

        # recommend recoit le filet categorie + le flag honnete
        _, kwargs = self.m_recommend.call_args
        self.assertTrue(kwargs["produit_sans_match_confirme"])
        cand = self.m_recommend.call_args.args[1]
        self.assertEqual([s.id for s in cand], [honey.id])
        # NB : l'exclusion effective du magasin de miel est le travail du LLM
        # (filtre de plausibilite du prompt) -> verifie en smoke test live.

    # ---- Catalogue confirme : on EXCLUT la categorie vaguement liee
    def test_foie_gras_avec_catalogue_exclut_categorie_non_pertinente(self):
        honey = make_store("Famille Mary", self.cat_epicerie,
                            desc="Produits de la ruche.")
        charc = make_store("Charcuterie Dupont", self.cat_charcuterie)
        add_product(charc, "Foie gras maison")
        self.m_extract.return_value = self._params(
            categories=[self.cat_epicerie.slug, self.cat_charcuterie.slug],
            idees_produits=["foie gras"],
        )
        resp, data = self._post("je veux du foie gras")

        _, kwargs = self.m_recommend.call_args
        self.assertFalse(kwargs["produit_sans_match_confirme"])
        cand_ids = [s.id for s in self.m_recommend.call_args.args[1]]
        self.assertIn(charc.id, cand_ids)
        self.assertNotIn(honey.id, cand_ids)       # filet categorie NON utilise
        ids_conf = self.m_recommend.call_args.args[2]
        self.assertEqual(ids_conf, {charc.id})     # seul le catalogue = confirme

    # ---- Tier description : preuve directe, pas de "aucune correspondance"
    def test_foie_gras_via_description(self):
        honey = make_store("Famille Mary", self.cat_epicerie,
                            desc="Produits de la ruche.")
        epic = make_store("Épicerie Lefevre", self.cat_epicerie,
                          desc="Nous proposons du foie gras et des terrines.")
        self.m_extract.return_value = self._params(
            categories=[self.cat_epicerie.slug], idees_produits=["foie gras"]
        )
        resp, data = self._post("je veux du foie gras")

        _, kwargs = self.m_recommend.call_args
        self.assertFalse(kwargs["produit_sans_match_confirme"])  # desc = preuve directe
        cand_ids = [s.id for s in self.m_recommend.call_args.args[1]]
        self.assertIn(epic.id, cand_ids)
        self.assertNotIn(honey.id, cand_ids)
        self.assertEqual(self.m_recommend.call_args.args[2], set())  # rien de confirme

    # ---- Demande non-produit (besoin/categorie) : produit d'abord, flag False
    def test_demande_categorie_simple(self):
        f = make_store("Fleurs & Co", self.cat_fleuriste)
        self.m_extract.return_value = self._params(
            categories=[self.cat_fleuriste.slug], idees_produits=[]
        )
        resp, data = self._post("un fleuriste")
        _, kwargs = self.m_recommend.call_args
        self.assertFalse(kwargs["produit_sans_match_confirme"])
        self.assertIn(f.id, [s.id for s in self.m_recommend.call_args.args[1]])

    # ---- Web saute quand pas de signal
    def test_web_saute_sans_signal(self):
        self.m_extract.return_value = self._params(
            categories=[self.cat_fleuriste.slug], idees_produits=[]
        )
        make_store("Fleurs & Co", self.cat_fleuriste)
        self._post("un fleuriste")
        self.m_understand.assert_not_called()
        # extract appele avec intent_text=None
        self.assertIsNone(self.m_extract.call_args.args[1])

    # ---- Web declenche sur signal
    def test_web_declenche_sur_signal(self):
        self.m_extract.return_value = self._params(
            categories=[self.cat_fleuriste.slug], idees_produits=[]
        )
        make_store("Fleurs & Co", self.cat_fleuriste)
        self._post("un fleuriste a offrir vu la météo")
        self.m_understand.assert_called_once()
        self.assertEqual(self.m_extract.call_args.args[1], "intention libre")

    # ---- Cache : 2e appel identique servi sans LLM ni quota
    def test_cache_hit_evite_llm_et_quota(self):
        make_store("Fleurs & Co", self.cat_fleuriste)
        self.m_extract.return_value = self._params(
            categories=[self.cat_fleuriste.slug], idees_produits=[]
        )
        _, data1 = self._post("un fleuriste")
        _, data2 = self._post("un fleuriste")
        self.assertEqual(data1, data2)
        self.assertEqual(self.m_recommend.call_count, 1)   # 2e = cache
        self.assertEqual(self.m_register.call_count, 1)     # quota non reconsomme

    # ---- "Ouvert maintenant" : jamais mis en cache
    def test_ouvert_maintenant_non_cache(self):
        make_store("Resto", self.cat_fleuriste, open_now=True)
        self.m_extract.return_value = self._params(
            categories=[self.cat_fleuriste.slug], idees_produits=[], ouvert_maintenant=True
        )
        self._post("un resto ouvert maintenant")
        self._post("un resto ouvert maintenant")
        self.assertEqual(self.m_recommend.call_count, 2)   # recalcule a chaque fois
        # Le contexte open-now est bien transmis a recommend_stores.
        self.assertTrue(self.m_recommend.call_args.kwargs["ouvert_maintenant"])


# =====================================================================
#  4. CABLAGE DU PROMPT (client, sans reseau)
# =====================================================================
class PromptWiringTests(TestCase):
    def _fake_client(self):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({
                    "intention": "produit_precis", "message": "m",
                    "pistes": [], "aucun_resultat": True,
                })
            ))]
        )
        client = SimpleNamespace(chat=SimpleNamespace(complete=lambda **kw: (
            self._captured.update(kw) or resp
        )))
        return client

    def setUp(self):
        self._captured = {}

    def _system_prompt(self):
        return self._captured["messages"][0]["content"]

    def test_bloc_cas_particulier_present_quand_flag(self):
        from members.ai_agent import client as client_mod
        with patch.object(client_mod, "_get_client", self._fake_client):
            client_mod.recommend_stores(
                "foie gras", [], set(), produit_sans_match_confirme=True
            )
        self.assertIn("CAS PARTICULIER", self._system_prompt())

    def test_bloc_cas_particulier_absent_par_defaut(self):
        from members.ai_agent import client as client_mod
        with patch.object(client_mod, "_get_client", self._fake_client):
            client_mod.recommend_stores(
                "foie gras", [], set(), produit_sans_match_confirme=False
            )
        self.assertNotIn("CAS PARTICULIER", self._system_prompt())

    def test_contexte_open_now_present_quand_flag(self):
        from members.ai_agent import client as client_mod
        with patch.object(client_mod, "_get_client", self._fake_client):
            client_mod.recommend_stores(
                "resto ouvert", [], set(), ouvert_maintenant=True
            )
        self.assertIn("OUVERT MAINTENANT", self._system_prompt())

    def test_contexte_open_now_absent_par_defaut(self):
        from members.ai_agent import client as client_mod
        with patch.object(client_mod, "_get_client", self._fake_client):
            client_mod.recommend_stores("resto", [], set())
        self.assertNotIn("OUVERT MAINTENANT", self._system_prompt())
