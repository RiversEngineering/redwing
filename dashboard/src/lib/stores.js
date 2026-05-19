/**
 * Svelte writable stores that hold the live robot state.
 *
 * ws.js delivers raw JSON messages; App.svelte routes them here.
 */

import { writable, derived } from 'svelte/store';

// ── Connection ────────────────────────────────────────────────────────────────
/** @type {import('svelte/store').Writable<boolean>} */
export const connected = writable(false);

// ── Robot state ───────────────────────────────────────────────────────────────
/**
 * Latest "state" message from the daemon.
 * Shape: { ts, uptime, ports: { "1": {type, ...}, ... } }
 * @type {import('svelte/store').Writable<object|null>}
 */
export const robotState = writable(null);

/**
 * Derived: flat port map, always 17 entries (IDs 0–16).
 * S0–S7 → IDs 0–7, D0–D7 → IDs 8–15, I2C → ID 16.
 * Each entry is null when not configured, or the port data object
 * augmented with a numeric `id` field.
 */
export const ports = derived(robotState, ($state) => {
  const result = {};
  for (let i = 0; i < 17; i++) {
    result[i] = null;
  }
  if ($state?.ports) {
    for (const [id, data] of Object.entries($state.ports)) {
      const numId = Number(id);
      if (numId >= 0 && numId < 17) {
        result[numId] = { ...data, id: numId };
      }
    }
  }
  return result;
});

// ── Log messages ──────────────────────────────────────────────────────────────
const MAX_LOG_LINES = 200;

/**
 * Array of log entries: { level, message, ts, id }
 * @type {import('svelte/store').Writable<Array>}
 */
export const logs = writable([]);

let _logId = 0;

export function pushLog(entry) {
  logs.update((prev) => {
    const next = [...prev, { ...entry, id: _logId++ }];
    return next.length > MAX_LOG_LINES ? next.slice(next.length - MAX_LOG_LINES) : next;
  });
}

export function clearLogs() {
  logs.set([]);
}

// ── Camera ────────────────────────────────────────────────────────────────────
/** Latest camera frame as a base64 JPEG string, or '' if none yet. */
export const cameraFrame = writable('');

// ── Uptime ────────────────────────────────────────────────────────────────────
/** Latest uptime value in seconds (float). */
export const uptime = derived(robotState, ($s) => $s?.uptime ?? null);
