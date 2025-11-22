document.addEventListener("DOMContentLoaded", function () {
    const partsInput = document.getElementById("id_parts_withdrawn");
    const fullItemsInput = document.getElementById("id_full_items");
    const partsRemainingInput = document.getElementById("id_parts_remaining");

    function updatePartCalculations() {
        const parts = parseInt(partsInput.value, 10) || 0;
        const threshold = parseInt(document.getElementById("id_units_per_quantity").value, 10) || 1;
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
