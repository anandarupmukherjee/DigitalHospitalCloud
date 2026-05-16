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
    const productFeatureInput = document.getElementById("id_product_feature");
    const unitsPerQuantityInput = document.getElementById("id_units_per_quantity");
    const accumulatedPartialInput = document.getElementById("id_accumulated_partial");
    const currentStockInput = document.getElementById("id_current_stock");
    const manualBehavior = document.getElementById("manual-withdrawal-behavior");
    const manualModeInput = document.getElementById("id_manual_withdrawal_mode");
    const manualTypeInput = document.getElementById("id_manual_withdrawal_type");
    const manualQcLink = document.getElementById("manual-qc-link");
    const quantityInput = document.getElementById("id_quantity");
    const partsInput = document.getElementById("id_parts_withdrawn");
    const fullItemSection = document.getElementById("full_item_section");
    const partItemSection = document.getElementById("part_item_section");
    let availableLots = [];

    function setFieldState(field, disabled) {
        if (!field) {
            return;
        }
        field.disabled = disabled;
        if (disabled) {
            field.value = field.tagName === "SELECT" ? "" : "0";
        }
    }

    function syncManualQcLink(selectedLot) {
        if (!manualQcLink) {
            return;
        }
        const shouldShow = Boolean(selectedLot && selectedLot.item_id && selectedLot.qc_action_required && !selectedLot.qc_passed);
        if (!shouldShow) {
            manualQcLink.style.display = "none";
            manualQcLink.href = "#";
            return;
        }
        manualQcLink.href = buildAppUrl(`/quality-control/checks/create/?product_item_id=${encodeURIComponent(selectedLot.item_id)}`);
        manualQcLink.style.display = "inline-flex";
    }

    function updateManualModeForLot(selectedLot) {
        if (!selectedLot) {
            if (manualBehavior) {
                manualBehavior.textContent = "Select a product and lot to load the withdrawal behavior.";
            }
            if (productFeatureInput) productFeatureInput.value = "";
            if (unitsPerQuantityInput) unitsPerQuantityInput.value = "";
            if (accumulatedPartialInput) accumulatedPartialInput.value = "0";
            if (currentStockInput) currentStockInput.value = "0";
            if (manualModeInput) manualModeInput.value = "full";
            if (manualTypeInput) manualTypeInput.value = "unit";
            if (fullItemSection) fullItemSection.style.display = "block";
            if (partItemSection) partItemSection.style.display = "none";
            setFieldState(quantityInput, false);
            setFieldState(partsInput, true);
            syncManualQcLink(null);
            document.dispatchEvent(new CustomEvent("manualLotChanged"));
            return;
        }

        const productFeature = selectedLot.product_feature || "unit";
        const unitsPerQuantity = selectedLot.units_per_quantity ?? "1";
        const accumulatedPartial = selectedLot.accumulated_partial ?? 0;
        const currentStock = selectedLot.current_stock ?? "0";
        const supportsPartial = productFeature === "volume" || Number(unitsPerQuantity) > 1;

        if (productFeatureInput) productFeatureInput.value = productFeature;
        if (unitsPerQuantityInput) unitsPerQuantityInput.value = unitsPerQuantity;
        if (accumulatedPartialInput) accumulatedPartialInput.value = accumulatedPartial;
        if (currentStockInput) currentStockInput.value = currentStock;

        if (supportsPartial) {
            if (manualModeInput) manualModeInput.value = "part";
            if (manualTypeInput) manualTypeInput.value = productFeature === "volume" ? "part" : "part";
            if (fullItemSection) fullItemSection.style.display = "none";
            if (partItemSection) partItemSection.style.display = "block";
            setFieldState(quantityInput, true);
            setFieldState(partsInput, false);
            if (partsInput && (!partsInput.value || partsInput.value === "0")) {
                partsInput.value = "1";
            }
            if (manualBehavior) {
                manualBehavior.textContent = productFeature === "volume"
                    ? "This lot uses fixed partial withdrawals. Enter the number of partial steps to withdraw."
                    : "This lot uses parts-based withdrawal. Enter the number of parts to withdraw.";
            }
        } else {
            if (manualModeInput) manualModeInput.value = "full";
            if (manualTypeInput) manualTypeInput.value = "unit";
            if (fullItemSection) fullItemSection.style.display = "block";
            if (partItemSection) partItemSection.style.display = "none";
            setFieldState(quantityInput, false);
            setFieldState(partsInput, true);
            if (quantityInput && (!quantityInput.value || quantityInput.value === "0")) {
                quantityInput.value = "1";
            }
            if (manualBehavior) {
                manualBehavior.textContent = "This lot uses full-item withdrawal only. Enter the number of items to withdraw.";
            }
        }

        syncManualQcLink(selectedLot);
        document.dispatchEvent(new CustomEvent("manualLotChanged"));
    }

    function clearManualLotOptions() {
        if (!manualLotDropdown) return;
        manualLotDropdown.innerHTML = '<option value="">-- Select Lot --</option>';
        availableLots = [];
        if (manualExpiryDisplay) manualExpiryDisplay.value = "";
        document.getElementById("manual-stock-display").textContent = "";
        document.getElementById("manual-units-display").textContent = "";
        document.getElementById("stock-display").textContent = "";
        document.getElementById("units-display").textContent = "";
        updateManualModeForLot(null);
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
            updateManualModeForLot(null);
            return;
        }

        if (manualExpiryDisplay) manualExpiryDisplay.value = selectedLot.expiry_date || "";
        document.getElementById("manual-stock-display").textContent = selectedLot.current_stock ?? "";
        document.getElementById("manual-units-display").textContent = selectedLot.units_per_quantity ?? "";
        document.getElementById("stock-display").textContent = selectedLot.current_stock ?? "";
        document.getElementById("units-display").textContent = selectedLot.units_per_quantity ?? "";
        updateManualModeForLot(selectedLot);
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

                document.getElementById("id_product_name").value = data.name || "";
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
                    } else {
                        updateManualModeForLot(null);
                    }
                }

            } catch (err) {
                console.error("Error fetching product by ID:", err);
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
