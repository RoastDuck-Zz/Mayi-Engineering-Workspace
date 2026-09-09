"use strict";

function generateClientId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  }

  return `client-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getOrCreateClientId() {
  const storedClientId = localStorage.getItem("robotdog-client-id");
  if (storedClientId) return storedClientId;
  const clientId = generateClientId();
  localStorage.setItem("robotdog-client-id", clientId);
  return clientId;
}

const state = {
  pin: sessionStorage.getItem("robotdog-pin") || "",
  clientId: getOrCreateClientId(),
  status: null,
  held: new Map(),
  motionTimer: null,
  speed: 0.35,
  pollStatusTimer: null,
  pageLeaving: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const pinDialog = $("#pin-dialog");
const pinForm = $("#pin-form");
const toast = $("#toast");

function notify(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => toast.classList.remove("visible"), 2800);
}

async function api(route, body = null, quiet = false, timeoutMs = 1800) {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(route, {
      method: body === null ? "GET" : "POST",
      headers: { "Content-Type": "application/json", "X-Control-Pin": state.pin },
      body: body === null ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || `请求失败 (${response.status})`);
    if (payload.status) renderStatus(payload.status);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") error = new Error("状态请求超时");
    if (!quiet) notify(error.message, true);
    throw error;
  } finally {
    clearTimeout(deadline);
  }
}

function formatNumber(value, digits = 2) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "--";
}

function renderStatus(status) {
  state.status = status;
  const connected = Boolean(status.connected);
  const ownsControl = status.controller_id === state.clientId;
  const ready = connected && !status.estopped && ownsControl;
  const chip = $("#robot-status");
  chip.classList.toggle("online", connected);
  chip.querySelector("span").textContent = connected ? "机器狗已连接" : "机器狗未连接";
  $("#robot-ip").textContent = status.robot_ip || "--";
  $("#connect-button").textContent = connected ? "断开机器狗" : "连接机器狗";
  $("#mode-label").textContent = String(status.mode || "--").toUpperCase();
  $("#watchdog-value").textContent = status.watchdog_ms ?? 3000;
  $("#motion-ttl-value").textContent = status.motion_command_ttl_ms ?? 300;

  const armed = $("#armed-state");
  armed.classList.toggle("locked", !ready);
  armed.querySelector("span").textContent = ready ? "运动已解锁" : "急停锁定";
  armed.disabled = !connected || (!status.estopped && !ownsControl);

  const battery = Number(status.battery);
  $("#battery").textContent = Number.isFinite(battery) ? `${Math.round(battery)}%` : "--%";
  $("#battery-bar").style.width = Number.isFinite(battery) ? `${Math.max(0, Math.min(100, battery))}%` : "0%";
  $("#motion-state").textContent = status.motion_state || "--";
  $("#gait").textContent = status.gait || "--";
  $("#safety-reason").textContent = status.estop_reason || "--";
  $("#controller-state").textContent = !status.controller_active ? "空闲" : ownsControl ? "本机控制" : "其他控制端占用";

  const velocity = status.velocity || {};
  const bodySpeed = Math.hypot(Number(velocity.x) || 0, Number(velocity.y) || 0);
  $("#body-speed").textContent = `${bodySpeed.toFixed(2)} m/s`;
  const imu = Array.isArray(status.imu_rpy) ? status.imu_rpy : [];
  $("#imu").textContent = `${formatNumber(imu[0], 1)} / ${formatNumber(imu[1], 1)} / ${formatNumber(imu[2], 1)}`;
  $("#temperature").textContent = `${formatNumber(status.max_motor_temperature, 1)} °C`;
  $$(".drive-key[data-axis], .action-button, #zero-button").forEach((button) => { button.disabled = !ready; });
  if (status.last_error) notify(`控制器故障：${status.last_error}`, true);
  renderVelocity(velocity);
}

function renderVelocity(command) {
  const signed = (value) => `${Number(value) >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}`;
  $("#velocity-readout").textContent = `X ${signed(command.x)}  Y ${signed(command.y)}  R ${signed(command.yaw)}`;
}

function currentCommand() {
  const command = { x: 0, y: 0, yaw: 0 };
  for (const control of state.held.values()) command[control.axis] += control.direction;
  command.x *= 0.6 * state.speed;
  command.y *= 0.35 * state.speed;
  command.yaw *= 0.9 * state.speed;
  // The physical Mymooo controller ignores smaller lateral commands.
  if (command.y && Math.abs(command.y) < 0.25) command.y = Math.sign(command.y) * 0.25;
  return command;
}

async function sendVelocity(command, quiet = false) {
  if (!state.status?.connected || state.status.estopped || state.status.controller_id !== state.clientId) return;
  try {
    await api("/api/velocity", { client_id: state.clientId, ...command }, quiet, 500);
  } catch (_) { /* api already reports interactive errors */ }
}

function updateLoop() {
  if (state.motionTimer !== null) return;
  const tick = () => sendVelocity(currentCommand(), true);
  tick();
  state.motionTimer = window.setInterval(tick, 100);
}

function holdStart(key, axis, direction) {
  state.held.set(key, { axis, direction });
  updateLoop();
}

function holdEnd(key) {
  state.held.delete(key);
  if (state.held.size === 0) clearMotion();
}

function clearMotion() {
  state.held.clear();
  if (state.motionTimer !== null) window.clearInterval(state.motionTimer);
  state.motionTimer = null;
  renderVelocity({ x: 0, y: 0, yaw: 0 });
  sendVelocity({ x: 0, y: 0, yaw: 0 }, true);
}

const keyMap = {
  KeyW: ["x", 1], KeyS: ["x", -1], KeyA: ["y", 1], KeyD: ["y", -1],
  KeyQ: ["yaw", 1], KeyE: ["yaw", -1],
};

$$(".drive-key[data-axis]").forEach((button) => {
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    holdStart(`pointer-${event.pointerId}`, button.dataset.axis, Number(button.dataset.direction));
  });
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) {
    button.addEventListener(name, (event) => holdEnd(`pointer-${event.pointerId}`));
  }
});

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input, textarea, select")) return;
  if (event.code === "Space") { event.preventDefault(); emergencyStop(); return; }
  const control = keyMap[event.code];
  if (control && !event.repeat) { event.preventDefault(); holdStart(`key-${event.code}`, ...control); }
});
document.addEventListener("keyup", (event) => { if (keyMap[event.code]) holdEnd(`key-${event.code}`); });

async function emergencyStop() {
  clearMotion();
  if (!state.status?.connected) return notify("机器狗尚未连接", true);
  try {
    await api("/api/estop", { client_id: state.clientId });
    notify("急停已触发：机器狗已停止");
  } catch (_) { /* api reported it */ }
}

$("#motion-stop").addEventListener("click", clearMotion);
$("#estop").addEventListener("click", emergencyStop);
$("#speed").addEventListener("input", (event) => {
  state.speed = Number(event.target.value) / 100;
  $("#speed-label").textContent = `${event.target.value}%`;
});

$("#connect-button").addEventListener("click", async () => {
  try {
    const route = state.status?.connected ? "/api/disconnect" : "/api/connect";
    await api(route, { client_id: state.clientId });
    notify(route.endsWith("disconnect") ? "机器狗已断开" : "机器狗已连接，请解除急停");
  } catch (_) { /* api reported it */ }
});

$("#armed-state").addEventListener("click", async () => {
  if (!state.status?.connected || !state.status.estopped) return;
  try { await api("/api/arm", { client_id: state.clientId }); notify("运动控制已解锁"); } catch (_) { /* api reported it */ }
});

$$(".action-button").forEach((button) => button.addEventListener("click", async () => {
  try { await api("/api/action", { client_id: state.clientId, name: button.dataset.action }); } catch (_) { /* api reported it */ }
}));

$("#zero-button").addEventListener("click", async () => {
  if (!$("#zero-confirm").checked) return notify("请先确认机器狗已处于标准趴卧姿态", true);
  try { await api("/api/action", { client_id: state.clientId, name: "zero", confirmed: true }); } catch (_) { /* api reported it */ }
});

pinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.pin = $("#pin-input").value.trim();
  try {
    await api("/api/status", null, true);
    sessionStorage.setItem("robotdog-pin", state.pin);
    $("#pin-error").textContent = "";
    pinDialog.close();
    runStatusPoll();
  } catch (error) { $("#pin-error").textContent = error.message; }
});

document.addEventListener("visibilitychange", () => { if (document.hidden) clearMotion(); });
window.addEventListener("blur", clearMotion);
window.addEventListener("pagehide", () => {
  state.pageLeaving = true;
  if (state.pollStatusTimer !== null) window.clearInterval(state.pollStatusTimer);
  if (state.motionTimer !== null) window.clearInterval(state.motionTimer);
  if (state.pin && state.status?.connected && !state.status.estopped && state.status.controller_id === state.clientId) {
    fetch("/api/velocity", {
      method: "POST", keepalive: true,
      headers: { "Content-Type": "application/json", "X-Control-Pin": state.pin },
      body: JSON.stringify({ client_id: state.clientId, x: 0, y: 0, yaw: 0 }),
    }).catch(() => {});
  }
});

async function pollStatus() {
  if (!state.pin || state.pageLeaving) return;
  const ownsControl = state.status?.controller_id === state.clientId;
  const route = state.status?.connected && !state.status?.estopped && ownsControl ? "/api/heartbeat" : "/api/status";
  try { await api(route, route === "/api/heartbeat" ? { client_id: state.clientId } : null, true); } catch (_) { /* retry next tick */ }
}

function runStatusPoll() {
  if (state.pollStatusTimer !== null) window.clearInterval(state.pollStatusTimer);
  pollStatus();
  state.pollStatusTimer = window.setInterval(pollStatus, 1000);
}

if (state.pin) runStatusPoll(); else pinDialog.showModal();
