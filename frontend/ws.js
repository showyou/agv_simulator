/**
 * ws.js — WebSocket クライアント
 * グローバル変数 `latestState` に最新状態を保持し、
 * renderMap / updateStats / appendLog を呼び出す。
 */

let ws = null;
let latestState = null;
let reconnectTimer = null;

function connectWS() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const url = `${protocol}://${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log("[WS] connected");
    document.getElementById("ws-status").textContent = "接続中";
    document.getElementById("ws-status").className = "status-ok";
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = (event) => {
    try {
      latestState = JSON.parse(event.data);
      renderMap(latestState);
      updateStats(latestState);
      appendLog(latestState);
      if (latestState.seed != null) {
        const el = document.getElementById("current-seed");
        if (el) el.textContent = latestState.seed;
      }
    } catch (e) {
      console.error("[WS] parse error", e);
    }
  };

  ws.onerror = (e) => {
    console.error("[WS] error", e);
  };

  ws.onclose = () => {
    console.log("[WS] disconnected, retry in 3s");
    document.getElementById("ws-status").textContent = "切断";
    document.getElementById("ws-status").className = "status-ng";
    reconnectTimer = setTimeout(connectWS, 3000);
  };
}

// ページロード時に接続
window.addEventListener("load", connectWS);
