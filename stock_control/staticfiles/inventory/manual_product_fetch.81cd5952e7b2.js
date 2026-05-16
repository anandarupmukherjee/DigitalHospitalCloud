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
    const manualLotDropdown = document.getElementById("id_manual_lot_item");
    const manualExpiryDisplay = document.getElementById("id_manual_expiry_display");
    let availableLots = [];

    function clearManualLotOptions() {
        if (!manualLotDropdown) return;
        manualLotDropdown.innerHTML = '<option value="">-- Select Lot --</option>';
        availableLots = [];
        if (manualExpiryDisplay) manualExpiryDisplay.value = "";
    }

    function applyLotSelection(itemId) {
        const selectedLot = availableLots.find(function (lot) {
            return String(lot.item_id) === String(itemId);
        });
        if (!selectedLot) {
            if (manualExpiryDisplay) manualExpiryDisplay.value = "";
            document.getElementById("manual-stock-display").textContent = "";
            document.getElementById("manual-units-display").textContent = "";
            document.getElementById("stock-display").textContent = "";
            document.getElementById("units-display").textContent = "";
            return;
        }

        if (manualExpiryDisplay) manualExpiryDisplay.value = selectedLot.expiry_date || "";
        document.getElementById("manual-stock-display").textContent = selectedLot.current_stock ?? "";
        document.getElementById("manual-units-display").textContent = selectedLot.units_per_quantity ?? "";
        document.getElementById("stock-display").textContent = selectedLot.current_stock ?? "";
        document.getElementById("units-display").textContent = selectedLot.units_per_quantity ?? "";
        document.getElementById("id_units_per_quantity").value = selectedLot.units_per_quantity ?? "";

        const volumeSection = document.getElementById("volume-withdrawal-section");
        if (selectedLot.product_feature === "volume" && volumeSection) {
            volumeSection.style.display = "block";
        } else if (volumeSection) {
            volumeSection.style.display = "none";
        }
    }

    if (productDropdown) {
        productDropdown.addEventListener("change", async function () {
            const selectedId = this.value;
            if (!selectedId) {
                clearManualLotOptions();
                return;
            }

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
                clearManualLotOptions();
                availableLots = data.lots || [];
                if (manualLotDropdown) {
                    availableLots.forEach(function (lot) {
                        const option = document.createElement("option");
                        option.value = String(lot.item_id);
                        option.textContent = `${lot.lot_number} | Exp ${lot.expiry_date} | Stock ${lot.current_stock}`;
                        manualLotDropdown.appendChild(option);
                    });
                    if (availableLots.length > 0) {
                        manualLotDropdown.value = String(availableLots[0].item_id);
                        applyLotSelection(manualLotDropdown.value);
                    }
                }

            } catch (err) {
                console.error("❌ Error fetching product by ID:", err);
                alert("Error fetching product info.");
            }
        });
    }

    if (manualLotDropdown) {
        manualLotDropdown.addEventListener("change", function () {
            applyLotSelection(this.value);
        });
    }
});
