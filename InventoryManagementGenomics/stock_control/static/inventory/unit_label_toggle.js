document.addEventListener("DOMContentLoaded", function () {
    const withdrawalType = document.getElementById("id_withdrawal_type");
    const unitLabel = document.getElementById("unit_label");

    if (withdrawalType && unitLabel) {
        withdrawalType.addEventListener("change", function () {
            unitLabel.textContent = withdrawalType.value === "volume" ? "mL" : "units";
        });
    }
});
