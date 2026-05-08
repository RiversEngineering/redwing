/**
 * WebSocket singleton with exponential-backoff auto-reconnect.
 *
 * Connects to ws://[current host]/ws and dispatches parsed JSON
 * messages to registered listeners.
 *
 * Reconnect delays: 1s → 2s → 4s → 8s → 16s (capped).
 */

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

let socket = null;
let reconnectAttempt = 0;
let reconnectTimer = null;
let destroyed = false;

/** @type {Set<(msg: object) => void>} */
const listeners = new Set();

/** @type {Set<(connected: boolean) => void>} */
const statusListeners = new Set();

let _connected = false;

function setConnected(v) {
  _connected = v;
  statusListeners.forEach((fn) => fn(v));
}

function getWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/ws`;
}

function connect() {
  if (destroyed) return;

  const url = getWsUrl();
  socket = new WebSocket(url);

  socket.addEventListener('open', () => {
    reconnectAttempt = 0;
    setConnected(true);
  });

  socket.addEventListener('message', (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      console.warn('[ws] bad JSON:', event.data);
      return;
    }
    listeners.forEach((fn) => fn(msg));
  });

  socket.addEventListener('close', () => {
    setConnected(false);
    scheduleReconnect();
  });

  socket.addEventListener('error', () => {
    // 'close' will fire right after; let that handle reconnect
    socket?.close();
  });
}

function scheduleReconnect() {
  if (destroyed) return;
  if (reconnectTimer) return; // already scheduled

  const delay = RECONNECT_DELAYS[Math.min(reconnectAttempt, RECONNECT_DELAYS.length - 1)];
  reconnectAttempt++;

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delay);
}

/** Add a message listener. Returns an unsubscribe function. */
export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Add a connection-status listener. Immediately called with current status. Returns unsubscribe. */
export function onStatus(fn) {
  fn(_connected);
  statusListeners.add(fn);
  return () => statusListeners.delete(fn);
}

/** Tear down – call on app destroy (rarely needed). */
export function destroy() {
  destroyed = true;
  clearTimeout(reconnectTimer);
  socket?.close();
}

// Start connecting immediately when this module is imported.
connect();
