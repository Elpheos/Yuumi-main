/**
 * copy_horaires.js
 * UX copier/coller entre jours dans l'admin Django - StoreAdmin.
 *
 * Placer dans : static/admin/js/copy_horaires.js
 * Référencer dans StoreAdmin via class Media (voir admin.py ci-dessous).
 *
 * Comportement :
 *  - Chaque jour a un bouton "Copier" et un bouton "Effacer".
 *  - Cliquer "Copier" sur un jour :
 *      → ce bouton devient "✓ Copié" (vert, style actif)
 *      → tous les autres jours voient leur bouton "Copier" devenir "⬇ Coller"
 *  - Cliquer "⬇ Coller" applique les horaires copiés sur ce jour.
 *    (on peut coller sur autant de jours qu'on veut)
 *  - Cliquer à nouveau sur "✓ Copié" ou appuyer sur Échap annule le mode copie.
 */

(function () {
  "use strict";

  const JOURS = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
  ];

  const SUFFIXES = [
    "matin_ouverture",
    "matin_fermeture",
    "apresmidi_ouverture",
    "apresmidi_fermeture",
  ];

  // État global
  let copiedJour = null;
  let copiedValues = null;

  // Références aux boutons { lundi: { copy: btn, clear: btn }, ... }
  const btns = {};

  /* ------------------------------------------------------------------ */
  /*  Lecture / écriture des champs                                       */
  /* ------------------------------------------------------------------ */

  function getValues(jour) {
    return SUFFIXES.map((suf) => {
      const el = document.getElementById(`id_${jour}_${suf}`);
      return el ? el.value : "";
    });
  }

  function setValues(jour, values) {
    SUFFIXES.forEach((suf, i) => {
      const el = document.getElementById(`id_${jour}_${suf}`);
      if (!el) return;
      el.value = values[i];
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function clearValues(jour) {
    setValues(jour, ["", "", "", ""]);
  }

  /* ------------------------------------------------------------------ */
  /*  Mode copie                                                          */
  /* ------------------------------------------------------------------ */

  function enterCopyMode(jour) {
    copiedJour = jour;
    copiedValues = getValues(jour);

    // Bouton source → "✓ Copié"
    const srcBtn = btns[jour].copy;
    srcBtn.textContent = "✓ Copié";
    srcBtn.classList.add("btn-horaires-copied");
    srcBtn.title = "Cliquer pour annuler";

    // Tous les autres → "⬇ Coller"
    JOURS.forEach((j) => {
      if (j === jour) return;
      const btn = btns[j].copy;
      btn.textContent = "⬇ Coller";
      btn.classList.add("btn-horaires-paste");
    });
  }

  function exitCopyMode() {
    if (!copiedJour) return;

    btns[copiedJour].copy.textContent = "Copier";
    btns[copiedJour].copy.classList.remove("btn-horaires-copied");
    btns[copiedJour].copy.title = "";

    JOURS.forEach((j) => {
      if (j === copiedJour) return;
      btns[j].copy.textContent = "Copier";
      btns[j].copy.classList.remove("btn-horaires-paste");
    });

    copiedJour = null;
    copiedValues = null;
  }

  function pasteToJour(jour) {
    if (!copiedValues) return;
    setValues(jour, copiedValues);

    // Flash vert sur les champs collés
    SUFFIXES.forEach((suf) => {
      const el = document.getElementById(`id_${jour}_${suf}`);
      if (!el) return;
      el.classList.add("horaires-field-flash");
      setTimeout(() => el.classList.remove("horaires-field-flash"), 700);
    });
  }

  /* ------------------------------------------------------------------ */
  /*  Toast                                                               */
  /* ------------------------------------------------------------------ */

  function showToast(msg) {
    let toast = document.getElementById("horaires-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "horaires-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("visible");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("visible"), 2000);
  }

  /* ------------------------------------------------------------------ */
  /*  Injection des boutons dans chaque fieldset de jour                 */
  /* ------------------------------------------------------------------ */

  function injectButtons() {
    JOURS.forEach((jour) => {
      // Trouver le fieldset dont le h2 correspond au jour
      let fs = null;
      document.querySelectorAll("fieldset").forEach((f) => {
        const h2 = f.querySelector("h2");
        if (h2 && h2.textContent.trim().toLowerCase() === jour) fs = f;
      });
      if (!fs || fs.querySelector(".horaires-btn-group")) return;

      const group = document.createElement("div");
      group.className = "horaires-btn-group";

      // --- Bouton Copier (état dynamique) ---
      const btnCopy = document.createElement("button");
      btnCopy.type = "button";
      btnCopy.className = "btn-horaires btn-horaires-copy";
      btnCopy.textContent = "Copier";

      btnCopy.addEventListener("click", () => {
        if (copiedJour === jour) {
          // Je suis la source → annuler le mode copie
          exitCopyMode();
          return;
        }
        if (copiedJour !== null) {
          // Un autre jour est copié → coller ici
          pasteToJour(jour);
          const label = jour.charAt(0).toUpperCase() + jour.slice(1);
          showToast(`Horaires de ${copiedJour} → ${label}`);
          return;
        }
        // Aucun mode copie actif → démarrer
        enterCopyMode(jour);
      });

      // --- Bouton Effacer ---
      const btnClear = document.createElement("button");
      btnClear.type = "button";
      btnClear.className = "btn-horaires btn-horaires-clear";
      btnClear.textContent = "Effacer";

      btnClear.addEventListener("click", () => {
        clearValues(jour);
        const label = jour.charAt(0).toUpperCase() + jour.slice(1);
        showToast(`${label} effacé`);
      });

      group.appendChild(btnCopy);
      group.appendChild(btnClear);

      fs.querySelector("h2").insertAdjacentElement("afterend", group);
      btns[jour] = { copy: btnCopy, clear: btnClear };
    });
  }

  /* ------------------------------------------------------------------ */
  /*  Styles                                                              */
  /* ------------------------------------------------------------------ */

  function injectStyles() {
    const style = document.createElement("style");
    style.textContent = `
      .horaires-btn-group {
        display: flex;
        gap: 8px;
        margin: 4px 12px 10px;
      }

      .btn-horaires {
        padding: 4px 14px;
        border-radius: 4px;
        border: 1px solid transparent;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: background 0.15s, color 0.15s;
      }

      /* --- Copier (état normal) --- */
      .btn-horaires-copy {
        background: #417690;
        color: #fff;
        border-color: #2c5470;
      }
      .btn-horaires-copy:hover {
        background: #2c5470;
      }

      /* --- ✓ Copié (source active) --- */
      .btn-horaires-copy.btn-horaires-copied {
        background: #2e7d32;
        border-color: #1b5e20;
        color: #fff;
      }
      .btn-horaires-copy.btn-horaires-copied:hover {
        background: #1b5e20;
      }

      /* --- ⬇ Coller (cibles disponibles) --- */
      .btn-horaires-copy.btn-horaires-paste {
        background: #f57c00;
        border-color: #e65100;
        color: #fff;
        animation: horaires-pulse 1.2s infinite;
      }
      .btn-horaires-copy.btn-horaires-paste:hover {
        background: #e65100;
        animation: none;
      }

      @keyframes horaires-pulse {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.75; }
      }

      /* --- Effacer --- */
      .btn-horaires-clear {
        background: #fff;
        color: #ba2121;
        border-color: #ba2121;
      }
      .btn-horaires-clear:hover {
        background: #ba2121;
        color: #fff;
      }

      /* --- Flash sur les champs collés --- */
      .horaires-field-flash {
        outline: 2px solid #2e7d32 !important;
        background: #e8f5e9 !important;
        transition: outline 0.7s, background 0.7s;
      }

      /* --- Toast --- */
      #horaires-toast {
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #323232;
        color: #fff;
        padding: 8px 18px;
        border-radius: 6px;
        font-size: 13px;
        opacity: 0;
        transform: translateY(6px);
        transition: opacity 0.2s, transform 0.2s;
        pointer-events: none;
        z-index: 99999;
      }
      #horaires-toast.visible {
        opacity: 1;
        transform: translateY(0);
      }
    `;
    document.head.appendChild(style);
  }

  /* ------------------------------------------------------------------ */
  /*  Raccourci Échap                                                     */
  /* ------------------------------------------------------------------ */

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && copiedJour) exitCopyMode();
  });

  /* ------------------------------------------------------------------ */
  /*  Init                                                                */
  /* ------------------------------------------------------------------ */

  function init() {
    injectStyles();
    injectButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
