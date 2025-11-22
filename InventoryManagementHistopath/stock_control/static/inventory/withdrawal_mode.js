document.addEventListener("DOMContentLoaded", function () {
    const withdrawalModeRadios = document.querySelectorAll('input[name="withdrawal_mode"]');
    const fullItemSection = document.getElementById("full_item_section");
    const partItemSection = document.getElementById("part_item_section");

    withdrawalModeRadios.forEach(radio => {
        radio.addEventListener("change", function () {
            fullItemSection.style.display = this.value === "full" ? "block" : "none";
            partItemSection.style.display = this.value === "part" ? "block" : "none";
        });
    });
});
