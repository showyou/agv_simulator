/**
 * map.js — Canvas描画 + 統計・ログ更新
 */

const CELL = 12; // 1グリッドのピクセルサイズ
const PADDING = 10;

// 配送完了エフェクト管理
const deliveryEffects = [];

function getCanvas() {
  return document.getElementById("map-canvas");
}

function worldToScreen(pos, mapH) {
  return [
    PADDING + pos[0] * CELL + CELL / 2,
    PADDING + pos[1] * CELL + CELL / 2,
  ];
}

/**
 * Canvas全体を再描画する
 */
function renderMap(state) {
  const canvas = getCanvas();
  if (!canvas) return;
  const map = state.map;

  canvas.width = PADDING * 2 + map.width * CELL;
  canvas.height = PADDING * 2 + map.height * CELL;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // グリッド背景
  drawGrid(ctx, map);

  // 顧客ノード
  for (const pos of map.customer_positions) {
    drawCircle(ctx, pos, map.height, 5, "#70AD47", "#4a7a30");
  }

  // 倉庫
  drawRect(ctx, map.warehouse_pos, map.height, 14, "#FF8C00", "#b36200");
  drawLabel(ctx, map.warehouse_pos, map.height, "倉", "#fff");

  // 商店
  drawRect(ctx, map.store_pos, map.height, 16, "#2E75B6", "#1a4a7a");
  drawLabel(ctx, map.store_pos, map.height, "店", "#fff");

  // AGVルート（破線）
  for (const agv of Object.values(state.agvs)) {
    if (agv.route && agv.route.length > 0) {
      drawRoute(ctx, agv.pos, agv.route, map.height);
    }
  }

  // AGV
  for (const agv of Object.values(state.agvs)) {
    drawAGV(ctx, agv, map.height);
  }

  // 配送完了エフェクト
  drawDeliveryEffects(ctx, map.height);
}

function drawGrid(ctx, map) {
  ctx.strokeStyle = "#2a2a2a";
  ctx.lineWidth = 0.3;
  for (let x = 0; x <= map.width; x++) {
    ctx.beginPath();
    ctx.moveTo(PADDING + x * CELL, PADDING);
    ctx.lineTo(PADDING + x * CELL, PADDING + map.height * CELL);
    ctx.stroke();
  }
  for (let y = 0; y <= map.height; y++) {
    ctx.beginPath();
    ctx.moveTo(PADDING, PADDING + y * CELL);
    ctx.lineTo(PADDING + map.width * CELL, PADDING + y * CELL);
    ctx.stroke();
  }
}

function drawRect(ctx, pos, mapH, size, fill, stroke) {
  const [sx, sy] = worldToScreen(pos, mapH);
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.rect(sx - size / 2, sy - size / 2, size, size);
  ctx.fill();
  ctx.stroke();
}

function drawCircle(ctx, pos, mapH, r, fill, stroke) {
  const [sx, sy] = worldToScreen(pos, mapH);
  ctx.fillStyle = fill;
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(sx, sy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

function drawLabel(ctx, pos, mapH, text, color) {
  const [sx, sy] = worldToScreen(pos, mapH);
  ctx.fillStyle = color;
  ctx.font = "bold 8px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, sx, sy);
}

function drawRoute(ctx, agvPos, route, mapH) {
  ctx.strokeStyle = "rgba(200,200,200,0.35)";
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  const [sx, sy] = worldToScreen(agvPos, mapH);
  ctx.moveTo(sx, sy);
  for (const p of route) {
    const [rx, ry] = worldToScreen(p, mapH);
    ctx.lineTo(rx, ry);
  }
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawAGV(ctx, agv, mapH) {
  const [sx, sy] = worldToScreen(agv.pos, mapH);
  const size = 7;

  const colorMap = {
    idle: "#AAAAAA",
    moving: "#FFD700",
    delivering: "#FF4444",
    charging: "#00BFFF",
  };
  const color = colorMap[agv.status] || "#AAAAAA";

  // 三角形
  ctx.fillStyle = color;
  ctx.strokeStyle = "#333";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(sx, sy - size);
  ctx.lineTo(sx - size * 0.8, sy + size * 0.6);
  ctx.lineTo(sx + size * 0.8, sy + size * 0.6);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // バッテリーインジケータ
  const bw = 10;
  const bh = 2;
  ctx.fillStyle = "#333";
  ctx.fillRect(sx - bw / 2, sy + size + 1, bw, bh);
  ctx.fillStyle = agv.battery > 0.3 ? "#4caf50" : "#f44336";
  ctx.fillRect(sx - bw / 2, sy + size + 1, bw * agv.battery, bh);
}

function drawDeliveryEffects(ctx, mapH) {
  const now = performance.now();
  for (let i = deliveryEffects.length - 1; i >= 0; i--) {
    const ef = deliveryEffects[i];
    const elapsed = now - ef.startTime;
    const duration = 800;
    if (elapsed > duration) {
      deliveryEffects.splice(i, 1);
      continue;
    }
    const progress = elapsed / duration;
    const r = 5 + 30 * progress;
    const alpha = 1 - progress;
    const [sx, sy] = worldToScreen(ef.pos, mapH);
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(100, 220, 100, ${alpha})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

// 配送完了エフェクトを追加（外部から呼ぶ）
function triggerDeliveryEffect(pos) {
  deliveryEffects.push({ pos, startTime: performance.now() });
}

// ---- 統計バー ----
let prevDelivered = 0;

function updateStats(state) {
  const s = state.stats;
  setEl("stat-delivered", s.delivered);
  setEl("stat-pending", s.pending);
  setEl("stat-failed", s.failed);
  setEl("stat-tick", state.tick);

  const activeAGVs = Object.values(state.agvs).filter(
    (a) => a.status === "moving" || a.status === "delivering"
  ).length;
  const chargingAGVs = Object.values(state.agvs).filter(
    (a) => a.status === "charging"
  ).length;
  setEl("stat-active-agvs", activeAGVs);
  setEl("stat-charging", chargingAGVs);
  setEl("stat-battery-dead", s.battery_dead ?? 0);

  // 配送完了エフェクトのトリガー
  if (s.delivered > prevDelivered) {
    // 完了した注文の座標を探してエフェクト
    for (const order of Object.values(state.orders)) {
      if (order.status === "delivered") {
        triggerDeliveryEffect(order.customer_pos);
      }
    }
  }
  prevDelivered = s.delivered;

  updateAGVBattery(state);
}

function updateAGVBattery(state) {
  const list = document.getElementById("agv-battery-list");
  if (!list) return;

  const statusColor = {
    idle: "#AAAAAA",
    moving: "#FFD700",
    delivering: "#FF4444",
    charging: "#00BFFF",
  };

  for (const [agvId, agv] of Object.entries(state.agvs)) {
    const rowId = "agv-row-" + agvId;
    let row = document.getElementById(rowId);

    if (!row) {
      // 行を新規作成
      row = document.createElement("div");
      row.id = rowId;
      row.className = "agv-battery-row";
      row.innerHTML = `
        <span class="agv-status-dot" id="${rowId}-dot"></span>
        <span class="agv-battery-label">${agvId}</span>
        <div class="agv-battery-bar-bg">
          <div class="agv-battery-bar" id="${rowId}-bar"></div>
        </div>
        <span class="agv-battery-pct" id="${rowId}-pct"></span>
      `;
      list.appendChild(row);
    }

    const pct = Math.round(agv.battery * 100);
    const bar = document.getElementById(`${rowId}-bar`);
    const pctEl = document.getElementById(`${rowId}-pct`);
    const dot = document.getElementById(`${rowId}-dot`);

    if (bar) {
      bar.style.width = pct + "%";
      bar.style.backgroundColor =
        pct > 50 ? "#4caf50" : pct > 20 ? "#FFD700" : "#f44336";
    }
    if (pctEl) pctEl.textContent = pct + "%";
    if (dot) dot.style.backgroundColor = statusColor[agv.status] || "#aaa";
  }
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ---- ログパネル ----
let lastLogTick = -1;

function appendLog(state) {
  if (!state.events || state.events.length === 0) return;
  const panel = document.getElementById("log-panel");
  if (!panel) return;

  const newEvents = state.events.filter((e) => e.tick > lastLogTick);
  for (const ev of newEvents) {
    const div = document.createElement("div");
    div.className = "log-entry";
    div.textContent = `[tick ${ev.tick}] ${ev.message}`;
    panel.prepend(div);
    lastLogTick = Math.max(lastLogTick, ev.tick);
  }

  // 最大50件
  while (panel.children.length > 50) {
    panel.removeChild(panel.lastChild);
  }
}
