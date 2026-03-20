(function () {
    function getBasePath() {
        if (typeof window.__APP_BASE_PATH === "string") {
            return window.__APP_BASE_PATH;
        }
        const dataset = document.body ? document.body.dataset || {} : {};
        const base = (dataset.rootUrl || "").replace(/\/+$/, "");
        window.__APP_BASE_PATH = base;
        return base;
    }

    const buildAppUrl =
        window.__buildAppUrl ||
        function (path) {
            const base = getBasePath();
            if (path[0] !== "/") {
                path = "/" + path;
            }
            return base ? `${base}${path}` : path;
        };

    window.__buildAppUrl = buildAppUrl;

    document.addEventListener("DOMContentLoaded", function () {
        const barcodeInput = document.getElementById("id_barcode");
        const productNameInput = document.getElementById("id_product_name");
        const productCodeVisible = document.getElementById("parsed_product_code");
        const productCodeHidden = document.getElementById("parsed_product_code_hidden");
        const resolvedProductUuid = document.getElementById("resolved_product_uuid");
        const lotVisible = document.getElementById("parsed_lot_number");
        const expiryVisible = document.getElementById("parsed_expiry_date");
        const lotHidden = document.getElementById("lot_number_field");
        const expiryHidden = document.getElementById("expiry_date_field");
        const stockDisplay = document.getElementById("stock-display");
        const unitsDisplay = document.getElementById("units-display");
        const unitsPerQuantityInput = document.getElementById("id_units_per_quantity");
        const volumeSection = document.getElementById("volume-withdrawal-section");

        if (!barcodeInput) return;
        let pendingResolveTimer = null;
        let lastResolvedBarcode = "";

        function resetResolvedFields() {
            if (productNameInput) productNameInput.value = "";
            if (productCodeVisible) productCodeVisible.value = "";
            if (productCodeHidden) productCodeHidden.value = "";
            if (resolvedProductUuid) resolvedProductUuid.value = "";
            if (lotVisible) lotVisible.value = "";
            if (expiryVisible) expiryVisible.value = "";
            if (lotHidden) lotHidden.value = "";
            if (expiryHidden) expiryHidden.value = "";
            if (stockDisplay) stockDisplay.textContent = "";
            if (unitsDisplay) unitsDisplay.textContent = "";
            if (unitsPerQuantityInput) unitsPerQuantityInput.value = "";
            if (volumeSection) volumeSection.style.display = "none";
        }

        function applyResolvedProduct(payload) {
            const product = payload.resolved_product || {};
            if (productNameInput) productNameInput.value = product.name || payload.name || "";
            if (productCodeVisible) {
                productCodeVisible.value =
                    payload.parsed?.raw_product_code ||
                    payload.parsed?.normalized_product_code ||
                    product.product_code ||
                    "";
            }
            if (productCodeHidden) {
                productCodeHidden.value =
                    payload.parsed?.raw_product_code ||
                    payload.parsed?.normalized_product_code ||
                    product.product_code ||
                    "";
            }
            if (resolvedProductUuid) resolvedProductUuid.value = product.id || "";
            if (lotVisible) lotVisible.value = payload.parsed?.lot_number || "";
            if (expiryVisible) expiryVisible.value = payload.parsed?.expiry_date || "";
            if (lotHidden) lotHidden.value = payload.parsed?.lot_number || "";
            if (expiryHidden) expiryHidden.value = payload.parsed?.expiry_date || "";
            if (stockDisplay) stockDisplay.textContent = payload.stock ?? "";
            if (unitsDisplay) unitsDisplay.textContent = payload.units_per_quantity ?? "";
            if (unitsPerQuantityInput) unitsPerQuantityInput.value = payload.units_per_quantity ?? "";
            if (volumeSection) {
                if (payload.product_feature === "volume") {
                    volumeSection.style.display = "block";
                } else {
                    volumeSection.style.display = "none";
                }
            }
        }

        function buildLookupUrls(rawBarcode) {
            const encoded = encodeURIComponent((rawBarcode || "").trim());
            const urls = [];
            urls.push(buildAppUrl(`/data/get-product-by-barcode/?barcode=${encoded}`));
            urls.push(`/data/get-product-by-barcode/?barcode=${encoded}`);
            if (window.location && window.location.pathname) {
                const fromData2 = window.location.pathname.replace(/\/data2\/.*/, "/data/");
                if (fromData2 !== window.location.pathname) {
                    urls.push(`${fromData2}get-product-by-barcode/?barcode=${encoded}`);
                }
            }
            return [...new Set(urls)];
        }

        async function fetchLookupPayload(rawBarcode) {
            const urls = buildLookupUrls(rawBarcode);
            let lastError = null;
            for (const url of urls) {
                try {
                    const response = await fetch(url, { headers: { Accept: "application/json" } });
                    const contentType = (response.headers.get("content-type") || "").toLowerCase();
                    if (!contentType.includes("application/json")) {
                        continue;
                    }
                    const payload = await response.json();
                    payload.__status = response.status;
                    return payload;
                } catch (err) {
                    lastError = err;
                }
            }
            if (lastError) {
                throw lastError;
            }
            throw new Error("Barcode lookup endpoint unavailable");
        }

        async function resolveBarcode(rawBarcode) {
            const normalized = (rawBarcode || "").trim();
            if (!normalized) return;
            const payload = await fetchLookupPayload(normalized);
            if (payload && payload.resolved_product && !payload.mapping_required) {
                applyResolvedProduct(payload);
                lastResolvedBarcode = normalized;
                return;
            }

            resetResolvedFields();
            if (payload && payload.parsed) {
                if (productCodeVisible) {
                    productCodeVisible.value =
                        payload.parsed.raw_product_code || payload.parsed.normalized_product_code || "";
                }
                if (productCodeHidden) {
                    productCodeHidden.value =
                        payload.parsed.raw_product_code || payload.parsed.normalized_product_code || "";
                }
                if (lotVisible) lotVisible.value = payload.parsed.lot_number || "";
                if (expiryVisible) expiryVisible.value = payload.parsed.expiry_date || "";
                if (lotHidden) lotHidden.value = payload.parsed.lot_number || "";
                if (expiryHidden) expiryHidden.value = payload.parsed.expiry_date || "";
            }
            alert("Barcode could not be mapped automatically. Please use manual selection or ask an inventory manager to add a mapping in Manage Product Codes.");
        }

        function scheduleResolve(value) {
            const rawBarcode = (value || "").trim();
            if (!rawBarcode || rawBarcode === lastResolvedBarcode) return;
            if (pendingResolveTimer) {
                clearTimeout(pendingResolveTimer);
            }
            pendingResolveTimer = setTimeout(async function () {
                try {
                    await resolveBarcode(rawBarcode);
                } catch (err) {
                    console.error("Barcode lookup failed:", err);
                }
            }, 120);
        }

        barcodeInput.addEventListener("keydown", async function (event) {
            if (event.key !== "Enter") return;
            event.preventDefault();
            const rawBarcode = barcodeInput.value.trim();
            if (!rawBarcode) return;
            try {
                await resolveBarcode(rawBarcode);
            } catch (err) {
                console.error("Barcode lookup failed:", err);
                alert("Failed to resolve barcode.");
            }
        });

        barcodeInput.addEventListener("change", function () {
            scheduleResolve(barcodeInput.value);
        });

        barcodeInput.addEventListener("input", function () {
            const rawBarcode = barcodeInput.value.trim();
            if (rawBarcode.length < 8) return;
            scheduleResolve(rawBarcode);
        });

        barcodeInput.addEventListener("blur", function () {
            scheduleResolve(barcodeInput.value);
        });
    });
})();
