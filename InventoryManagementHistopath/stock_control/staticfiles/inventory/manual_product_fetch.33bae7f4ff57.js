function ensureBuildAppUrl() {
    if (window.__buildAppUrl) {
        return window.__buildAppUrl;
    }
    const helper = function (path) {
        const dataset = document.body ? document.body.dataset || {} : {};
        const base = (window.__APP_BASE_PATH ||
            (window.__APP_BASE_PATH = (dataset.rootUrl || "").replace(/\/+$/, ""))) || "";
        if (path[0] !== "/") {
            path = "/" + path;
        }
        return base ? `${base}${path}` : path;
    };
    window.__buildAppUrl = helper;
    return helper;
}

const buildAppUrl = ensureBuildAppUrl();

document.addEventListener("DOMContentLoaded", function () {
    const productDropdown = document.getElementById("id_product_dropdown");

    if (productDropdown) {
        productDropdown.addEventListener("change", async function () {
            const selectedId = this.value;
            if (!selectedId) return;

            try {
                const response = await fetch(
                    buildAppUrl(`/data/get-product-by-id/?id=${encodeURIComponent(selectedId)}`)
                );
                if (!response.ok) throw new Error("Product not found");

                const data = await response.json();

                // Fill common fields
                document.getElementById("id_product_name").value = data.name || "";
                document.getElementById("stock-display").textContent = data.current_stock ?? "";
                document.getElementById("units-display").textContent = data.units_per_quantity ?? "";
                document.getElementById("id_units_per_quantity").value = data.units_per_quantity ?? "";

                // Fill manual fields
                document.getElementById("id_barcode_manual").value = data.product_code || "";
                document.getElementById("manual-stock-display").textContent = data.current_stock ?? "";
                document.getElementById("manual-units-display").textContent = data.units_per_quantity ?? "";

                // Toggle volume section
                const volumeSection = document.getElementById("volume-withdrawal-section");
                if (data.product_feature === "volume" && volumeSection) {
                    volumeSection.style.display = "block";
                } else {
                    volumeSection.style.display = "none";
                }

            } catch (err) {
                console.error("❌ Error fetching product by ID:", err);
                alert("Error fetching product info.");
            }
        });
    }
});
