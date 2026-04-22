async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(payload.detail || "请求失败");
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function setStatus(message, type = "info") {
  const banner = document.getElementById("status-banner");
  if (!banner) {
    return;
  }

  banner.textContent = message;
  banner.classList.remove("hidden", "status-error", "status-success", "status-info");
  banner.classList.add(`status-${type}`);
}

function setButtonsDisabled(disabled) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach((button) => {
    button.disabled = disabled;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const addForm = document.getElementById("add-watchlist-form");
  const symbolInput = document.getElementById("symbol-input");
  const refreshButton = document.getElementById("refresh-button");
  const reportButton = document.getElementById("report-button");

  addForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const symbol = symbolInput?.value?.trim();
    if (!symbol) {
      setStatus("请输入股票代码。", "error");
      return;
    }

    try {
      setButtonsDisabled(true);
      setStatus("正在添加自选股...", "info");
      await requestJson("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ symbol }),
      });
      window.location.reload();
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      setButtonsDisabled(false);
    }
  });

  refreshButton?.addEventListener("click", async () => {
    try {
      setButtonsDisabled(true);
      setStatus("正在刷新行情，请稍候...", "info");
      const payload = await requestJson("/api/refresh", { method: "POST" });
      setStatus(`刷新完成，共更新 ${payload.count} 只股票。`, "success");
      window.location.reload();
    } catch (error) {
      setStatus(error.message, "error");
      setButtonsDisabled(false);
    }
  });

  reportButton?.addEventListener("click", async () => {
    try {
      setButtonsDisabled(true);
      setStatus("正在生成 AI 日报，请稍候...", "info");
      const payload = await requestJson("/api/reports/generate", { method: "POST" });
      window.location.href = payload.redirect_url;
    } catch (error) {
      setStatus(error.message, "error");
      setButtonsDisabled(false);
    }
  });

  document.querySelectorAll(".delete-watchlist-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const { symbol } = button.dataset;
      if (!symbol) {
        return;
      }

      try {
        setButtonsDisabled(true);
        setStatus(`正在删除 ${symbol}...`, "info");
        await requestJson(`/api/watchlist/${symbol}`, { method: "DELETE" });
        window.location.reload();
      } catch (error) {
        setStatus(error.message, "error");
        setButtonsDisabled(false);
      }
    });
  });
});
