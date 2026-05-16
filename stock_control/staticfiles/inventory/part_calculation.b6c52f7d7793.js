document.addEventListener("DOMContentLoaded", function () {
    const partsInput = document.getElementById("id_parts_withdrawn");
    const fullItemsInput = document.getElementById("id_full_items");
    const partsRemainingInput = document.getElementById("id_parts_remaining");
    const withdrawalType = document.getElementById("id_withdrawal_type");

    function updatePartCalculations() {
        const parts = parseInt(partsInput.value, 10) || 0;
        const threshold = parseFloat(document.getElementById("id_units_per_quantity").value) || 1;

        if (withdrawalType && withdrawalType.value === "volume") {
            fullItemsInput.value = (parts * threshold).toFixed(2);
            partsRemainingInput.value = "";
            return;
        }

        const fullItems = Math.floor(parts / threshold);
        const remainder = parts % threshold;
        fullItemsInput.value = fullItems;
        partsRemainingInput.value = remainder === 0 && parts > 0 ? 0 : threshold - remainder;
    }

    if (partsInput) {
        partsInput.addEventListener("input", updatePartCalculations);
        updatePartCalculations();
    }
});
