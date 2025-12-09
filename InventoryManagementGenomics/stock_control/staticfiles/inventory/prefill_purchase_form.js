document.addEventListener("DOMContentLoaded", function () {
    const orderButtons = document.querySelectorAll(".order-now-btn");
    const nameField = document.getElementById("order-product-name");
    const codeField = document.getElementById("order-product-code");

    orderButtons.forEach(button => {
        button.addEventListener("click", function () {
            const row = button.closest("tr");
            const productCode = row.querySelector(".product-code-cell").textContent.trim();
            const productName = row.querySelector(".product-name-cell").textContent.trim();

            nameField.value = productName;
            codeField.value = productCode;

            // Optionally scroll to the form
            nameField.scrollIntoView({ behavior: "smooth", block: "center" });
        });
    });
});