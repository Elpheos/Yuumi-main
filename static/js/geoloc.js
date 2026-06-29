/**
 * geoloc.js — Yuumi
 * Gère la demande de permission géolocalisation avec un rationale
 * affiché AVANT la popup système (requis par Apple et Google).
 *
 * FLOW :
 * 1. On vérifie si la permission est déjà accordée
 * 2. Si pas encore demandée → on affiche une modale Yuumi explicative
 * 3. L'utilisateur accepte → on déclenche la popup système native
 * 4. Si refus → on continue sans géoloc, sans casser l'app
 */

const YUUMI_GEOLOC = (function () {

    const PERMISSION_KEY = 'yuumi_geoloc_asked';

    function isNative() {
        return window.Capacitor && window.Capacitor.isNativePlatform();
    }

    // ─── Vérifie le statut actuel de la permission ────────────────
    async function checkPermission() {
        try {
            const result = await Capacitor.Plugins.Geolocation.checkPermissions();
            return result.location; // 'granted', 'denied', 'prompt'
        } catch (e) {
            return 'denied';
        }
    }

    // ─── Demande la permission système ────────────────────────────
    async function requestPermission() {
        try {
            const result = await Capacitor.Plugins.Geolocation.requestPermissions();
            return result.location === 'granted';
        } catch (e) {
            return false;
        }
    }

    // ─── Affiche la modale rationale avant la popup système ───────
    function showRationaleModal(onAccept, onDeny) {
        const existing = document.getElementById('yuumi-geoloc-modal');
        if (existing) return;

        const modal = document.createElement('div');
        modal.id = 'yuumi-geoloc-modal';
        modal.style.cssText = `
            position: fixed;
            inset: 0;
            z-index: 99998;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: flex-end;
            justify-content: center;
            animation: fadeInOverlay 0.2s ease;
        `;

        modal.innerHTML = `
            <style>
                @keyframes fadeInOverlay {
                    from { opacity: 0; }
                    to   { opacity: 1; }
                }
                @keyframes slideUpModal {
                    from { transform: translateY(100%); }
                    to   { transform: translateY(0); }
                }
            </style>
            <div style="
                background: white;
                border-radius: 20px 20px 0 0;
                padding: 32px 24px calc(32px + env(safe-area-inset-bottom));
                width: 100%;
                max-width: 500px;
                text-align: center;
                animation: slideUpModal 0.3s ease;
                box-shadow: 0 -4px 24px rgba(0,0,0,0.15);
            ">
                <div style="font-size: 56px; margin-bottom: 16px;">📍</div>
                <h2 style="font-size: 1.3rem; font-weight: 800; color: #333; margin-bottom: 12px;">
                    Yuumi utilise votre position
                </h2>
                <p style="font-size: 0.9rem; color: #888; line-height: 1.7; margin-bottom: 28px;">
                    Pour afficher les commerces <strong>près de vous</strong>,
                    calculer les distances et filtrer par rayon,
                    Yuumi a besoin d'accéder à votre localisation.<br><br>
                    Votre position n'est <strong>jamais stockée</strong> ni partagée.
                </p>
                <button id="yuumi-geoloc-accept" style="
                    width: 100%;
                    background: #ff8b38;
                    color: white;
                    border: none;
                    border-radius: 12px;
                    padding: 15px;
                    font-size: 1rem;
                    font-weight: 700;
                    cursor: pointer;
                    margin-bottom: 10px;
                    font-family: inherit;
                ">
                    Autoriser la localisation
                </button>
                <button id="yuumi-geoloc-deny" style="
                    width: 100%;
                    background: none;
                    border: none;
                    color: #aaa;
                    font-size: 0.9rem;
                    cursor: pointer;
                    padding: 10px;
                    font-family: inherit;
                ">
                    Non merci
                </button>
            </div>
        `;

        document.body.appendChild(modal);

        document.getElementById('yuumi-geoloc-accept').addEventListener('click', () => {
            modal.remove();
            if (window.Capacitor?.Plugins?.Haptics) {
                Capacitor.Plugins.Haptics.impact({ style: 'LIGHT' });
            }
            onAccept();
        });

        document.getElementById('yuumi-geoloc-deny').addEventListener('click', () => {
            modal.remove();
            onDeny();
        });
    }

    // ─── Point d'entrée principal ──────────────────────────────────
    // Retourne les coords si permission accordée, null sinon
    //
    // Strategie : haute precision (GPS), avec un timeout assez long
    // pour laisser le temps au GPS d'accrocher (un "cold start" peut
    // prendre 15-30s, surtout en exterieur peu degage). La precision
    // compte plus que la rapidite pour cette app (filtre par rayon,
    // "commerces pres de vous").
    async function getPosition() {
        if (!isNative()) {
            // Sur web → comportement classique
            return new Promise((resolve) => {
                navigator.geolocation.getCurrentPosition(
                    pos => resolve(pos.coords),
                    () => resolve(null),
                    { enableHighAccuracy: true, timeout: 25000 }
                );
            });
        }

        const status = await checkPermission();

        if (status === 'granted') {
            // Permission déjà accordée → on récupère direct
            try {
                const pos = await Capacitor.Plugins.Geolocation.getCurrentPosition({
                    enableHighAccuracy: true,
                    timeout: 25000,
                });
                return pos.coords;
            } catch (e) {
                console.log("GEOLOC ERROR:", JSON.stringify(e), e.message);
                return null;
            }
        }

        if (status === 'denied') {
            // Permission refusée définitivement → on ne redemande pas
            return null;
        }

        // status === 'prompt' → première fois, on affiche le rationale
        return new Promise((resolve) => {
            showRationaleModal(
                async () => {
                    // L'utilisateur a accepté le rationale → popup système
                    localStorage.setItem(PERMISSION_KEY, '1');
                    const granted = await requestPermission();
                    if (granted) {
                        try {
                            const pos = await Capacitor.Plugins.Geolocation.getCurrentPosition({
                                enableHighAccuracy: true,
                                timeout: 25000,
                            });
                            resolve(pos.coords);
                        } catch (e) {
                            console.log("GEOLOC ERROR prompt:", JSON.stringify(e), e.message);
                            resolve(null);
                        }
                    } else {
                        resolve(null);
                    }
                },
                () => {
                    // L'utilisateur a refusé le rationale
                    localStorage.setItem(PERMISSION_KEY, '1');
                    resolve(null);
                }
            );
        });
    }

    return { getPosition };

})();
