document.addEventListener("DOMContentLoaded", function () {
    const barcodeInput = document.getElementById("id_barcode");

    if (!barcodeInput) return;


    barcodeInput.addEventListener("keydown", async function (event) {
        if (event.key !== "Enter") return;

        event.preventDefault(); // Prevent form submit
        const rawBarcode = barcodeInput.value.trim();
        if (rawBarcode.length < 10) return;

        try {
            // Step 1: Parse barcode to get product_code, lot_number, expiry_date
            const response = await fetch(`/data/parse-barcode/?raw=${encodeURIComponent(rawBarcode)}`);
            if (!response.ok) throw new Error("Barcode parsing failed");
            const data = await response.json();

            // Step 2: Fill parsed barcode details
            document.getElementById("parsed_product_code").value = data.product_code || "";
            document.getElementById("parsed_lot_number").value = data.lot_number || "";
            document.getElementById("parsed_expiry_date").value = data.expiry_date || "";

            document.getElementById("lot_number_field").value = data.lot_number || "";
            document.getElementById("expiry_date_field").value = data.expiry_date || "";
            document.getElementById("parsed_product_code_hidden").value = data.raw_product_code || data.product_code || "";

            // Step 3: Fetch and populate full product details
            const candidates = [data.raw_product_code, data.product_code, data.normalized_product_code].filter(Boolean);

            for (const code of candidates) {
                try {
                    const productResponse = await fetch(`/data/get-product-by-barcode/?barcode=${code}`);
                    if (!productResponse.ok) {
                        console.warn("⚠️ Product not found for code:", code);
                        continue;
                    }

                    const product = await productResponse.json();

                    document.getElementById("id_product_name").value = product.name || "";
                    document.getElementById("stock-display").textContent = product.stock ?? "";
                    document.getElementById("units-display").textContent = product.units_per_quantity ?? "";
                    document.getElementById("id_units_per_quantity").value = product.units_per_quantity ?? "";
                    document.getElementById("parsed_product_code_hidden").value = data.product_code || "";

                    const volumeSection = document.getElementById("volume-withdrawal-section");
                    if (product.product_feature === "volume" && volumeSection) {
                        volumeSection.style.display = "block";
                    } else if (volumeSection) {
                        volumeSection.style.display = "none";
                    }
                    break;
                } catch (fetchErr) {
                    console.error("❌ Failed to fetch product details:", fetchErr);
                }
            }

        } catch (err) {
            console.error("❌ Error processing barcode:", err);
            alert("❌ Failed to process barcode. Ensure format is correct.");
        }
    });
});
