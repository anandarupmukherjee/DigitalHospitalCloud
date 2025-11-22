document.addEventListener("DOMContentLoaded", function () {
    console.log("📦 DOM fully loaded");

    // --- 1) Mode Toggle: Barcode vs. Manual ---
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const barcodeSection = document.getElementById("barcode-section");
    const manualSection = document.getElementById("manual-section");
    const barcodeInput = document.getElementById("id_barcode");

    modeRadios.forEach(radio => {
        radio.addEventListener("change", function () {
            const isBarcode = this.value === "barcode";
            if (barcodeSection && manualSection) {
                barcodeSection.style.display = isBarcode ? "block" : "none";
                manualSection.style.display = isBarcode ? "none" : "block";
            }
            if (isBarcode && barcodeInput) barcodeInput.focus();
        });
    });

    // Focus if default mode is barcode
    if (barcodeInput) {
        const defaultMode = document.querySelector('input[name="mode"]:checked');
        if (defaultMode && defaultMode.value === "barcode") {
            barcodeInput.focus();
        }
    }

    // --- 2) Withdrawal Mode Toggle: Full vs. Part ---
    const withdrawalRadios = document.querySelectorAll('input[name="withdrawal_mode"]');
    const fullItemSection = document.getElementById("full_item_section");
    const partItemSection = document.getElementById("part_item_section");

    withdrawalRadios.forEach(radio => {
        radio.addEventListener("change", function () {
            if (fullItemSection && partItemSection) {
                fullItemSection.style.display = this.value === "full" ? "block" : "none";
                partItemSection.style.display = this.value === "part" ? "block" : "none";
            }
        });
    });

    // --- 3) Barcode Auto-Fill ---
    async function fetchProductDetailsByBarcode(barcode) {
        try {
            const response = await fetch(`/data/get-product-by-barcode/?barcode=${barcode}`);
            if (!response.ok) throw new Error("Product not found");
            const data = await response.json();

            document.getElementById("id_product_name").value = data.name || "";
            document.getElementById("stock-display").textContent = data.stock ?? "";
            document.getElementById("units-display").textContent = data.units_per_quantity ?? "";
            document.getElementById("id_units_per_quantity").value = data.units_per_quantity ?? "";

            const volumeSection = document.getElementById("volume-withdrawal-section");
            if (data.product_feature === "volume" && volumeSection) {
                volumeSection.style.display = "block";
            } else {
                volumeSection.style.display = "none";
            }
        } catch (err) {
            console.error("❌ Barcode fetch error:", err);
        }
    }

    if (barcodeInput) {
        barcodeInput.addEventListener("input", function () {
            const val = barcodeInput.value.trim();
            if (val.length > 3) fetchProductDetailsByBarcode(val);
        });
    }

    // --- 4) Manual Product Fetch ---
    const fetchButton = document.getElementById("fetch-manual-details");
    const productDropdown = document.getElementById("id_product_dropdown");

    if (fetchButton && productDropdown) {
        fetchButton.addEventListener("click", async function () {
            const productId = productDropdown.value;
            if (!productId) return alert("Please select a product first.");
            try {
                const response = await fetch(`/get-product-by-id/?id=${productId}`);
                if (!response.ok) throw new Error("Product not found");
                const data = await response.json();

                document.getElementById("id_product_name").value = data.name || "";
                document.getElementById("stock-display").textContent = data.current_stock ?? "";
                document.getElementById("units-display").textContent = data.units_per_quantity ?? "";
                document.getElementById("id_units_per_quantity").value = data.units_per_quantity ?? "";

                document.getElementById("id_barcode_manual").value = data.product_code || "";
                document.getElementById("manual-stock-display").textContent = data.current_stock ?? "";
                document.getElementById("manual-units-display").textContent = data.units_per_quantity ?? "";

                const volumeSection = document.getElementById("volume-withdrawal-section");
                if (data.product_feature === "volume" && volumeSection) {
                    volumeSection.style.display = "block";
                } else {
                    volumeSection.style.display = "none";
                }

                console.log("✅ Manual product details loaded");
            } catch (err) {
                console.error("❌ Manual fetch error:", err);
                alert("Error fetching product details.");
            }
        });
    }

    // --- 5) Withdrawal type label toggle ---
    const withdrawalType = document.getElementById("id_withdrawal_type");
    const unitLabel = document.getElementById("unit_label");
    if (withdrawalType && unitLabel) {
        withdrawalType.addEventListener("change", function () {
            unitLabel.textContent = withdrawalType.value === "volume" ? "mL" : "units";
        });
    }

    // --- 6) Partial Item Logic ---
    const partsInput = document.getElementById("id_parts_withdrawn");
    const fullItems = document.getElementById("id_full_items");
    const partsRemain = document.getElementById("id_parts_remaining");
    const unitsPerItem = document.getElementById("id_units_per_quantity");

    function updatePartCalc() {
        if (!partsInput || !fullItems || !partsRemain || !unitsPerItem) return;

        const parts = parseInt(partsInput.value || "0", 10);
        const threshold = parseInt(unitsPerItem.value || "1", 10);
        const full = Math.floor(parts / threshold);
        const remain = parts % threshold;

        fullItems.value = full;
        partsRemain.value = remain === 0 && parts > 0 ? 0 : threshold - remain;
    }

    if (partsInput) {
        partsInput.addEventListener("input", updatePartCalc);
        updatePartCalc();
    }

    console.log("✅ Script initialized completely.");
});
