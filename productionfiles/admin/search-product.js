document.addEventListener("DOMContentLoaded", function() {
    const toggle = document.getElementById("search-product-toggle");
    const container = document.getElementById("search-product-container");
    const input = document.getElementById("search-product-input");
    const results = document.getElementById("search-product-results");

    if (!toggle || !container || !input || !results) return;

    container.style.position = 'absolute';
    container.style.background = 'white';
    container.style.padding = '10px';
    container.style.border = '1px solid #ccc';
    container.style.zIndex = '1000';
    container.style.width = '300px';
    container.style.display = 'none';
    container.style.maxHeight = '400px';
    container.style.overflowY = 'auto';

    toggle.addEventListener("click", function(e) {
        e.preventDefault();
        container.style.display = container.style.display === "none" ? "block" : "none";
        if (container.style.display === "block") input.focus();
    });

    input.addEventListener("input", function() {
        const query = input.value.trim();
        if (query.length < 2) {
            results.innerHTML = "";
            return;
        }

        fetch(toggle.dataset.url + "?q=" + encodeURIComponent(query))
            .then(res => res.json())
            .then(data => {
                results.innerHTML = "";
                if (!data.length) {
                    results.innerHTML = "<p>Aucun résultat</p>";
                    return;
                }
                data.forEach(item => {
                    const div = document.createElement("div");
                    div.classList.add("derniers-arrivants-grid-commerces");

                    
                    div.innerHTML = `
                        <a href="${item.url}" rel="noopener">
                            <img src="${item.photo || '/static/placeholder.png'}" alt="Photo de ${item.store}" />
                            <h4>${item.store}</h4>
                        </a>
                    `;
                    results.appendChild(div);
                });
            })
            .catch(err => {
                console.error("Erreur recherche :", err);
                results.innerHTML = "<p>Erreur lors de la recherche</p>";
            });
    });

    document.addEventListener("click", function(e) {
        if (!container.contains(e.target) && e.target !== toggle) {
            container.style.display = "none";
        }
    });
});
