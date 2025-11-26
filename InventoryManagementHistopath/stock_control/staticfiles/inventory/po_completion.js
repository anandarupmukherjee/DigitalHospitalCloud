console.log("✅ JS file is loaded and running");

document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ DOM fully loaded");


  const form = document.getElementById("po-completion-form");
  if (!form) {
    console.warn("❌ Completion form not found");
    return;
  }
  console.log("✅ Completion form found");

  // 🧹 Hide Delivered rows older than 2 days
  document.querySelectorAll(".po-row").forEach(row => {
    const status = row.dataset.status;
    const deliveredAt = row.dataset.deliveredAt;

    if (status === "Delivered" && deliveredAt) {
      const deliveredDate = new Date(deliveredAt);
      const now = new Date();
      const diffInDays = (now - deliveredDate) / (1000 * 60 * 60 * 24); // ms to days

      if (diffInDays > 2) {
        row.style.display = "none";
        console.log(`🧹 Hiding row for ${row.dataset.productCode} (Delivered ${diffInDays.toFixed(1)} days ago)`);
      }
    }
  });


  // 🔄 Fetch product name by code
  async function fetchProductName(productCode) {
    if (!productCode) return;
    try {
      const res = await fetch(`/data/get-product-by-barcode/?barcode=${productCode}`);
      const data = await res.json();
      document.getElementById("id_product_name").value = data.name || "";
    } catch (err) {
      console.error("❌ Fetch error:", err);
    }
  }

  // 🖱️ Fill form when 'Complete' button is clicked
  document.querySelectorAll(".fill-form-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const code = btn.dataset.productCode;
      const quantity = btn.dataset.quantity;

      document.getElementById("id_product_code").value = code;
      document.getElementById("id_quantity_ordered").value = quantity;
      document.getElementById("id_status").value = "Delivered";

      fetchProductName(code);
    });
  });

  // 📦 Barcode input → auto-fill form
  const barcodeInput = document.getElementById("po-barcode");
  barcodeInput?.addEventListener("change", async () => {
    const raw = barcodeInput.value.trim();
    if (!raw) return;

    try {
      const res = await fetch(`/data/parse-barcode/?raw=${encodeURIComponent(raw)}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      document.getElementById("id_barcode").value = raw;
      document.getElementById("id_lot_number").value = data.lot_number || "";

      if (data.expiry_date) {
        const [d, m, y] = data.expiry_date.split(".");
        document.getElementById("id_expiry_date").value = `${y}-${m}-${d}`;
      }

      document.getElementById("id_product_code").value = data.product_code || "";
      fetchProductName(data.product_code);
    } catch (err) {
      alert("Failed to parse barcode: " + err.message);
      console.error("❌ Barcode parse failed:", err);
    }
  });

  // ✏️ Live update when manually editing product code
  const productCodeInput = document.getElementById("id_product_code");
  productCodeInput?.addEventListener("change", () => {
    fetchProductName(productCodeInput.value.trim());
  });

  // 🚀 AJAX submit form + update table
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    console.log("📨 AJAX form submit triggered");

    const formData = new FormData(form);
    const productCode = document.getElementById("id_product_code").value.trim();

    try {
      const res = await fetch(window.location.href, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      });

      if (!res.ok) throw new Error("Form submit failed");

      // 🔍 Find matching row
      const row = document.querySelector(`tr[data-product-code="${productCode}"]`);
      if (row) {
        console.log("✅ Row found:", row);

        row.querySelector("td:nth-child(5)").innerHTML = '<span class="status-delivered">✅ Delivered</span>';
        row.querySelector("td:nth-child(6)").innerHTML = '<span class="text-muted">Complete</span>';
        row.classList.remove("delayed-row");

        // 🌟 Optional: visual highlight
        row.style.transition = "background-color 0.5s";
        row.style.backgroundColor = "#d4edda";
        setTimeout(() => row.style.backgroundColor = "", 1500);
      } else {
        console.warn("⚠️ No matching row found for:", productCode);
      }

      form.reset();
    } catch (err) {
      alert("❌ Submit error: " + err.message);
      console.error(err);
    }
  });
});

