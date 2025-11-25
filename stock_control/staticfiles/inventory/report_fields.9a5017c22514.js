document.addEventListener("DOMContentLoaded", function () {
    const modelSelector = document.getElementById("report_type");
    const fieldContainer = document.getElementById("field-container");
  
    const modelFields = {
      withdrawals: ["timestamp", "product_code", "product_name", "quantity", "withdrawal_type", "barcode", "user"],
      stock: ["product_code", "name", "supplier", "threshold", "lead_time"],
      purchase_orders: ["product_code", "product_name", "quantity_ordered", "order_date", "expected_delivery", "status", "ordered_by"]
    };
  
    function updateFields() {
      const selectedModel = modelSelector.value;
      const fields = modelFields[selectedModel] || [];
      fieldContainer.innerHTML = "";
  
      fields.forEach(field => {
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.name = "fields";
        checkbox.value = field;
        checkbox.id = `field_${field}`;
        checkbox.checked = true;
  
        const label = document.createElement("label");
        label.htmlFor = checkbox.id;
        label.textContent = field.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  
        const wrapper = document.createElement("div");
        wrapper.className = "checkbox-field";
        wrapper.appendChild(checkbox);
        wrapper.appendChild(label);
  
        fieldContainer.appendChild(wrapper);
      });
    }
  
    if (modelSelector && fieldContainer) {
      modelSelector.addEventListener("change", updateFields);
      updateFields();
    }
  });
  