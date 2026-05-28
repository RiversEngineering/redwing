<script>
  /**
   * GraphPanel – up to 4 rolling 30-second uPlot graphs.
   *
   * Auto-populates as ports become configured:
   *   - encoder velocity   (per encoder port)
   *   - ultrasonic distance in cm  (per ultrasonic port)
   *   - motor speed %      (per motor port)
   */
  import { onDestroy } from 'svelte';
  import { robotState } from '../lib/stores.js';
  import GraphSeries from './GraphSeries.svelte';

  const WINDOW_S   = 30;       // rolling window in seconds
  const MAX_POINTS = 30 * 60;  // 60 Hz × 30 s — hard upper bound
  const MAX_GRAPHS = 4;

  const PALETTE = ['#60a5fa', '#a78bfa', '#34d399', '#fb923c'];

  /**
   * seriesList: Array<{ key, label, unit, color, times[], values[] }>
   * Reactive — triggers re-render of the {#each} block.
   */
  let seriesList = [];

  /** Map key → series object (same references as in seriesList) */
  const seriesMap = {};

  const unsubState = robotState.subscribe((state) => {
    if (!state?.ports) return;

    // ts field from daemon is integer ms (RP2040 uptime tick); fall back to wall clock
    const nowSec = Date.now() / 1000;

    let listChanged = false;

    for (const [portId, portData] of Object.entries(state.ports)) {
      const { type } = portData;
      let key, value, label, unit;

      if (type === 'encoder') {
        key   = `encoder_${portId}`;
        // velocity is stored as ticks/s × 10 for one decimal of precision
        value = +((portData.velocity ?? 0) / 10).toFixed(1);
        label = `P${portId} encoder`;
        unit  = 'ticks/s';
      } else if (type === 'ultrasonic') {
        if (!portData.valid) continue;
        key   = `ultrasonic_${portId}`;
        value = +(portData.distance_mm / 10).toFixed(1);
        label = `P${portId} distance`;
        unit  = 'cm';
      } else if (type === 'vl53l0x') {
        if (!portData.valid) continue;
        key   = `vl53l0x_${portId}`;
        value = +(portData.distance_mm / 10).toFixed(1);
        label = 'I²C ToF';
        unit  = 'cm';
      } else if (type === 'motor_sm' || type === 'motor_lap' || type === 'motor_servo_signal') {
        key   = `motor_${portId}`;
        value = +((portData.value ?? 0) / 100).toFixed(1);
        label = `P${portId} motor`;
        unit  = '%';
      } else if (type === 'servo') {
        key   = `servo_${portId}`;
        value = +(((portData.pulse_us ?? 1500) - 500) / 2000 * 300).toFixed(1);
        label = `P${portId} servo`;
        unit  = '°';
      } else {
        continue;
      }

      if (!seriesMap[key]) {
        if (seriesList.length >= MAX_GRAPHS) continue;
        const color = PALETTE[seriesList.length % PALETTE.length];
        const s = { key, label, unit, color, times: [], values: [] };
        seriesMap[key] = s;
        seriesList = [...seriesList, s]; // new array → Svelte reactive update
        listChanged = true;
      }

      const s = seriesMap[key];
      s.times.push(nowSec);
      s.values.push(value);

      // Trim old data outside rolling window
      const cutoff = nowSec - WINDOW_S;
      while (s.times.length > 0 && s.times[0] < cutoff) {
        s.times.shift();
        s.values.shift();
      }
      if (s.times.length > MAX_POINTS) {
        s.times.splice(0, s.times.length - MAX_POINTS);
        s.values.splice(0, s.values.length - MAX_POINTS);
      }

      // Signal the child component to re-render (reassign to trigger reactivity)
      // We achieve this by updating a 'tick' counter stored on the series object.
      // GraphSeries watches s.times / s.values via a prop callback.
      s._tick = (s._tick ?? 0) + 1;
    }

    if (!listChanged) {
      // Trigger reactivity for existing series data updates
      seriesList = seriesList; // no-op assignment forces Svelte to re-check bindings
    }
  });

  onDestroy(() => {
    unsubState();
  });
</script>

<div class="flex flex-col h-full bg-[#1e2129] rounded-lg border border-[#2e3340] overflow-hidden">
  <!-- Header -->
  <div class="flex items-center gap-2 px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline points="1,12 5,7 8,9 12,4 15,6"
                stroke="currentColor" stroke-width="1.2"
                stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Graphs</span>
    <span class="ml-auto text-[10px] text-slate-600">{WINDOW_S}s window</span>
  </div>

  <!-- Graph list -->
  <div class="flex-1 overflow-y-auto min-h-0 flex flex-col gap-1 p-1.5">
    {#if seriesList.length === 0}
      <div class="flex flex-col items-center justify-center h-full gap-2 text-slate-700">
        <svg class="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.2" stroke-linecap="round">
          <polyline points="3,17 8,12 12,14 17,9 21,11"/>
          <line x1="3" y1="20" x2="21" y2="20"/>
        </svg>
        <span class="text-sm">No sensors yet</span>
        <span class="text-xs text-slate-800">Graphs appear as ports are configured</span>
      </div>
    {:else}
      {#each seriesList as s (s.key)}
        <div class="flex-1 min-h-[90px]">
          <GraphSeries
            label={s.label}
            unit={s.unit}
            color={s.color}
            times={s.times}
            values={s.values}
            windowSec={WINDOW_S}
            tick={s._tick}
          />
        </div>
      {/each}
    {/if}
  </div>
</div>
