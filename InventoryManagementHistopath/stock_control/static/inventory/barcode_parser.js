const barcodeInput = document.getElementById("id_barcode");

if (barcodeInput) {
    barcodeInput.addEventListener("change", async function () {
        const barcode = barcodeInput.value.trim();
        if (!barcode) return;

        try {
            const response = await fetch(`/data/parse-barcode/?raw=${encodeURIComponent(barcode)}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Fetch failed");

            // Populate form fields if they exist
            if (document.getElementById("id_product_name")) {
                document.getElementById("id_product_name").value = data.name || "";
            }
            if (document.getElementById("stock-display")) {
                document.getElementById("stock-display").textContent = data.current_stock ?? "";
            }
            if (document.getElementById("units-display")) {
                document.getElementById("units-display").textContent = data.units_per_quantity ?? "";
            }
            if (document.getElementById("id_units_per_quantity")) {
                document.getElementById("id_units_per_quantity").value = data.units_per_quantity ?? "";
            }

            // Populate visible fields (if present)
            if (document.getElementById("id_lot_number")) {
                document.getElementById("id_lot_number").value = data.lot_number ?? "";
            }
            if (document.getElementById("id_expiry_date")) {
                document.getElementById("id_expiry_date").value = data.expiry_date ?? "";
            }

            // ✅ Also populate hidden fields for POST submission
            const codeHidden = document.getElementById("product_code_from_barcode");
            const lotHidden = document.getElementById("lot_number_field");
            const expiryHidden = document.getElementById("expiry_date_field");

            if (codeHidden) codeHidden.value = data.product_code || "";
            if (lotHidden) lotHidden.value = data.lot_number || "";
            if (expiryHidden) expiryHidden.value = data.expiry_date || "";

            // Volume-specific UI logic
            const volumeSection = document.getElementById("volume-withdrawal-section");
            if (data.product_feature === "volume" && volumeSection) {
                volumeSection.style.display = "block";
            } else if (volumeSection) {
                volumeSection.style.display = "none";
            }

        } catch (err) {
            alert("Barcode parsing failed: " + err.message);
            console.error(err);
        }
    });
}
