function buildVolumeSeries(data) {
  return data.volume.map((value, index) => ({
    value,
    itemStyle: {
      color: data.candles[index][1] >= data.candles[index][0] ? "#ef4444" : "#16a34a",
    },
  }));
}

function initPriceChart(data) {
  const element = document.getElementById("price-chart");
  if (!element) {
    return;
  }

  const chart = echarts.init(element);
  chart.setOption({
    animation: false,
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: { data: ["K线", "MA5", "MA10", "MA20", "MA60", "成交量"] },
    grid: [
      { left: 48, right: 24, top: 42, height: "56%" },
      { left: 48, right: 24, top: "72%", height: "14%" },
    ],
    xAxis: [
      { type: "category", data: data.dates, scale: true, boundaryGap: false, axisLine: { onZero: false } },
      { type: "category", gridIndex: 1, data: data.dates, scale: true, boundaryGap: false, axisLabel: { show: false }, axisTick: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, scale: true, splitNumber: 2 },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: "slider", xAxisIndex: [0, 1], top: "90%", start: 60, end: 100 },
    ],
    series: [
      { name: "K线", type: "candlestick", data: data.candles },
      { name: "MA5", type: "line", data: data.ma5, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "MA10", type: "line", data: data.ma10, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "MA20", type: "line", data: data.ma20, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "MA60", type: "line", data: data.ma60, smooth: true, showSymbol: false, lineStyle: { width: 1 } },
      { name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: buildVolumeSeries(data) },
    ],
  });

  window.addEventListener("resize", () => chart.resize());
}

function initMacdChart(data) {
  const element = document.getElementById("macd-chart");
  if (!element) {
    return;
  }

  const chart = echarts.init(element);
  chart.setOption({
    animation: false,
    tooltip: { trigger: "axis" },
    legend: { data: ["MACD", "Signal", "Histogram"] },
    xAxis: { type: "category", data: data.dates, boundaryGap: false },
    yAxis: { scale: true },
    dataZoom: [{ type: "inside", start: 60, end: 100 }],
    series: [
      {
        name: "Histogram",
        type: "bar",
        data: data.macd_hist.map((value) => ({
          value,
          itemStyle: { color: (value || 0) >= 0 ? "#ef4444" : "#16a34a" },
        })),
      },
      { name: "MACD", type: "line", data: data.macd, showSymbol: false },
      { name: "Signal", type: "line", data: data.macd_signal, showSymbol: false },
    ],
  });

  window.addEventListener("resize", () => chart.resize());
}

function initRsiChart(data) {
  const element = document.getElementById("rsi-chart");
  if (!element) {
    return;
  }

  const chart = echarts.init(element);
  chart.setOption({
    animation: false,
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: data.dates, boundaryGap: false },
    yAxis: { min: 0, max: 100 },
    dataZoom: [{ type: "inside", start: 60, end: 100 }],
    series: [
      {
        name: "RSI14",
        type: "line",
        data: data.rsi14,
        showSymbol: false,
        markLine: {
          symbol: "none",
          label: { formatter: "{b}" },
          data: [
            { yAxis: 70, name: "70" },
            { yAxis: 30, name: "30" },
          ],
        },
      },
    ],
  });

  window.addEventListener("resize", () => chart.resize());
}

async function bootstrapStockDetail() {
  const config = window.stockDetailConfig;
  if (!config || typeof echarts === "undefined") {
    return;
  }

  try {
    const response = await fetch(config.chartUrl);
    if (!response.ok) {
      throw new Error("图表数据加载失败");
    }
    const payload = await response.json();
    initPriceChart(payload);
    initMacdChart(payload);
    initRsiChart(payload);
  } catch (error) {
    ["price-chart", "macd-chart", "rsi-chart"].forEach((id) => {
      const element = document.getElementById(id);
      if (element) {
        element.innerHTML = `<div class="chart-error">${error.message}</div>`;
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", bootstrapStockDetail);
