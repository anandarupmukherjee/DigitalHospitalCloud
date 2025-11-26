document.addEventListener("DOMContentLoaded", function () {

    function getChartData(canvasId) {
        const element = document.getElementById(canvasId);
        if (!element) {
            console.error(`Element with ID '${canvasId}' not found.`);
            return null;
        }
        try {
            return {
                labels: JSON.parse(element.getAttribute("data-labels") || "[]"),
                stock: JSON.parse(element.getAttribute("data-stock") || "[]"),
                thresholds: JSON.parse(element.getAttribute("data-thresholds") || "[]"),
                dates: JSON.parse(element.getAttribute("data-dates") || "[]"),
                withdrawals: JSON.parse(element.getAttribute("data-withdrawals") || "[]"),
                sma7: JSON.parse(element.getAttribute("data-sma7") || "[]"),
                sma14: JSON.parse(element.getAttribute("data-sma14") || "[]"),
                forecastDates: JSON.parse(element.getAttribute("data-forecast-dates") || "[]"),
                forecastValues: JSON.parse(element.getAttribute("data-forecast-values") || "[]"),
                names: JSON.parse(element.getAttribute("data-names") || "[]"),
                leadTimes: JSON.parse(element.getAttribute("data-lead-times") || "[]"),
                runOutDays: JSON.parse(element.getAttribute("data-run-out-days") || "[]"),
                reorderDays: JSON.parse(element.getAttribute("data-reorder-days") || "[]"),
                topConsumedNames: JSON.parse(element.getAttribute("data-names") || "[]"),
                topConsumedQuantities: JSON.parse(element.getAttribute("data-quantities") || "[]")
            };
        } catch (error) {
            console.error(`Error parsing data for '${canvasId}':`, error);
            return null;
        }
    }

    function renderChart(canvasId, chartType, datasets, labels) {
        const ctx = document.getElementById(canvasId);
        if (ctx) {
            new Chart(ctx.getContext("2d"), {
                type: chartType,
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    },
                    plugins: {
                        legend: { display: true },
                        title: {
                            display: true,
                            text: canvasId.replace(/([A-Z])/g, ' $1').trim()
                        }
                    }
                }
            });
        }
    }

    // ✅ Render Stock Levels Chart
    const stockData = getChartData("stockLevelsChart");
    if (stockData) {
        renderChart("stockLevelsChart", "bar", [
            { label: "Current Stock", data: stockData.stock, backgroundColor: "blue" },
            { label: "Threshold", data: stockData.thresholds, backgroundColor: "red" }
        ], stockData.labels);
    }

    // ✅ Render Withdrawals Over Time Chart
    const withdrawalData = getChartData("withdrawalsOverTimeChart");
    if (withdrawalData) {
        renderChart("withdrawalsOverTimeChart", "line", [
            { label: "Total Withdrawals", data: withdrawalData.withdrawals, borderColor: "green", fill: false }
        ], withdrawalData.dates);
    }

    // ✅ Render Forecast Chart
    const forecastData = getChartData("forecastChart");
    if (forecastData) {
        renderChart("forecastChart", "line", [
            { label: "7-Day SMA", data: forecastData.sma7, borderColor: "orange", fill: false },
            { label: "14-Day SMA", data: forecastData.sma14, borderColor: "red", fill: false },
            { label: "Forecast (Next 7 Days)", data: forecastData.forecastValues, borderColor: "purple", borderDash: [5, 5], fill: false }
        ], [...forecastData.dates, ...forecastData.forecastDates]);
    }

    // ✅ Render Lead Times Chart
    const leadTimesData = getChartData("leadTimesChart");
    if (leadTimesData) {
        renderChart("leadTimesChart", "bar", [
            { label: "Lead Time (Days)", data: leadTimesData.leadTimes, backgroundColor: "blue" }
        ], leadTimesData.names);
    }

    // ✅ Render Run-Out Forecast Chart
    const runOutData = getChartData("runOutForecastChart");
    if (runOutData) {
        renderChart("runOutForecastChart", "bar", [
            { label: "Days Until Run-Out", data: runOutData.runOutDays, backgroundColor: "red" },
            { label: "Days Until Reorder", data: runOutData.reorderDays, backgroundColor: "orange" }
        ], runOutData.names);
    }

    // ✅ Render Top Consumed Items Chart
    const topConsumedData = getChartData("topConsumedItemsChart");
    if (topConsumedData) {
        renderChart("topConsumedItemsChart", "bar", [
            { label: "Top 5 Consumed Items", data: topConsumedData.topConsumedQuantities, backgroundColor: "purple" }
        ], topConsumedData.topConsumedNames);
    }

});
