window.addEventListener("load", function () {
    const searchProduct = document.getElementById("searchProduct");
    const searchWithdrawal = document.getElementById("searchWithdrawal");
    const searchAdmin = document.getElementById("searchAdmin");  // ✅ new
    const productTable = document.getElementById("productTable");
    const withdrawalTable = document.getElementById("withdrawalTable");
    const adminTable = document.getElementById("adminTable");  // ✅ new
    const searchLowStock = document.getElementById("searchLowStock");
    const lowStockTable = document.getElementById("lowStockTable");

    console.log("🔍 Checking elements:");
    console.log("🔍 searchProduct:", searchProduct ? "✅ Found" : "❌ Not Found");
    console.log("🔍 productTable:", productTable ? "✅ Found" : "❌ Not Found");
    console.log("🔍 searchWithdrawal:", searchWithdrawal ? "✅ Found" : "❌ Not Found");
    console.log("🔍 withdrawalTable:", withdrawalTable ? "✅ Found" : "❌ Not Found");
    console.log("🔍 searchAdmin:", searchAdmin ? "✅ Found" : "❌ Not Found");
    console.log("🔍 adminTable:", adminTable ? "✅ Found" : "❌ Not Found");
    console.log("🔍 searchLowStock:", searchLowStock ? "✅ Found" : "❌ Not Found");
    console.log("🔍 lowStockTable:", lowStockTable ? "✅ Found" : "❌ Not Found");

    function setupTableSearch(searchInputId, tableId, columnIndexes) {
        const searchInput = document.getElementById(searchInputId);
        const table = document.getElementById(tableId);

        if (!searchInput || !table) {
            console.error(`❌ Error: Missing elements for search in ${tableId}`);
            return;
        }

        console.log(`🔍 Setting up search for table: ${tableId}`);

        searchInput.addEventListener("keyup", function () {
            const filterValue = searchInput.value.toLowerCase();
            const tableBody = table.getElementsByTagName("tbody")[0];
            const rows = tableBody.getElementsByTagName("tr");

            for (let row of rows) {
                const cells = row.getElementsByTagName("td");
                let match = false;

                columnIndexes.forEach(index => {
                    if (cells[index] && cells[index].textContent.toLowerCase().includes(filterValue)) {
                        match = true;
                    }
                });

                row.style.display = match ? "" : "none";
            }
        });

        console.log(`✅ Search enabled for table: ${tableId}`);
    }

    if (searchProduct && productTable) {
        setupTableSearch("searchProduct", "productTable", [0, 1, 7]); // Adjust to actual table
    }

    if (searchWithdrawal && withdrawalTable) {
        setupTableSearch("searchWithdrawal", "withdrawalTable", [1, 5, 6]);
    }

    if (searchAdmin && adminTable) {
        setupTableSearch("searchAdmin", "adminTable", [0, 1]); // e.g., Code, Name, Supplier
    }
    
    if (searchLowStock && lowStockTable) {
        setupTableSearch("searchLowStock", "lowStockTable", [0, 1]); // Code, Name
    }
    


});

