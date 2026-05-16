document.addEventListener("DOMContentLoaded", function () {
    const partsInput = document.getElementById("id_parts_withdrawn");
    const fullItemsInput = document.getElementById("id_full_items");
    const partsRemainingInput = document.getElementById("id_parts_remaining");
    const productFeatureInput = document.getElementById("id_product_feature");
    const unitsPerQuantityInput = document.getElementById("id_units_per_quantity");
    const accumulatedPartialInput = document.getElementById("id_accumulated_partial");
    const currentStockInput = document.getElementById("id_current_stock");

    function formatDecimal(value) {
        const rounded = Number(value || 0).toFixed(2);
        return rounded.replace(/\.00$/, "").replace(/(\.\d)0$/, "$1");
    }

    function updatePartCalculations() {
        if (!partsInput || !fullItemsInput || !partsRemainingInput) {
            return;
        }

        const parts = parseInt(partsInput.value, 10) || 0;
        const threshold = parseFloat(unitsPerQuantityInput ? unitsPerQuantityInput.value : "") || 1;
        const productFeature = productFeatureInput ? productFeatureInput.value : "unit";
        const currentStock = parseFloat(currentStockInput ? currentStockInput.value : "") || 0;
        const accumulatedPartial = parseInt(accumulatedPartialInput ? accumulatedPartialInput.value : "", 10) || 0;

        if (productFeature === "volume") {
            const volumeToWithdraw = parts * threshold;
            const remainingVolume = Math.max(0, currentStock - volumeToWithdraw);
            const remainingSteps = threshold > 0 ? Math.floor(remainingVolume / threshold) : 0;
            fullItemsInput.value = `${formatDecimal(volumeToWithdraw)} mL`;
            partsRemainingInput.value = `${remainingSteps} partial step${remainingSteps === 1 ? "" : "s"}`;
            return;
        }

        const totalUnits = accumulatedPartial + parts;
        const fullItems = Math.floor(totalUnits / threshold);
        const remainder = totalUnits % threshold;
        const remainingParts = remainder === 0 && parts > 0 ? 0 : threshold - remainder;
        fullItemsInput.value = `${fullItems} full item${fullItems === 1 ? "" : "s"}`;
        partsRemainingInput.value = `${remainingParts} part${remainingParts === 1 ? "" : "s"}`;
    }

    if (partsInput) {
        partsInput.addEventListener("input", updatePartCalculations);
    }
    document.addEventListener("manualLotChanged", updatePartCalculations);
    updatePartCalculations();
});
