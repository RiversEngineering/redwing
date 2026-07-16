<script>
  /**
   * DataGraph – a single configurable multi-series rolling graph.
   *
   * Props:
   *   allSeries   {object}   key → { label, unit, color, values[] } — aligned to parent timeline
   *   timeline    {number[]} shared Unix-second timestamps (mutated in place by parent)
   *   windowSec   {number}   display window in seconds (shared between both graphs)
   *   nowSec      {number}   current time reference — changing this triggers a data redraw
   *   graphLabel  {string}   header label ("Graph 1" / "Graph 2")
   */
  export let allSeries = {};
  export let timeline = [];
  export let windowSec = 30;
  export let nowSec = 0;
  export let graphLabel = 'Graph';

  import { onMount, onDestroy } from 'svelte';
  import uPlot from 'uplot';

  let containerEl;
  let plot = null;
  let mounted = false;
  let selectedKeys = new Set();
  let lastValues = {};  // key → most recent non-null value, updated each data tick

  $: seriesKeys = Object.keys(allSeries).sort();

  // ── Series selection ─────────────────────────────────────────────────────────

  function toggleSeries(key) {
    if (selectedKeys.has(key)) selectedKeys.delete(key);
    else selectedKeys.add(key);
    selectedKeys = new Set(selectedKeys); // new ref → Svelte detects change
    if (mounted) rebuildPlot();
  }

  function getSelectedSeries() {
    return [...selectedKeys].filter((k) => allSeries[k]).map((k) => allSeries[k]);
  }

  // ── uPlot helpers ─────────────────────────────────────────────────────────────

  function getSize() {
    if (!containerEl) return { w: 300, h: 120 };
    return {
      w: Math.max(60, containerEl.clientWidth),
      h: Math.max(40, containerEl.clientHeight),
    };
  }

  // Each selected series gets its own y-scale so series with very different
  // value ranges (e.g. encoder ticks vs motor %) don't squish each other.
  function scaleKey(i) { return i === 0 ? 'y' : `y${i}`; }

  function makeRange() {
    return (u, min, max) => {
      if (!isFinite(min) || !isFinite(max)) return [-1, 1];
      const pad = Math.max(1, (max - min) * 0.1) || 1;
      return [min - pad, max + pad];
    };
  }

  function buildOpts(selected, w, h) {
    const scales = { x: { time: true } };
    for (let i = 0; i < selected.length; i++) {
      scales[scaleKey(i)] = { auto: true, range: makeRange() };
    }

    return {
      width: w,
      height: h,
      cursor: { show: false },
      select: { show: false },
      legend: { show: false },
      padding: [6, 8, 0, 0],
      scales,
      axes: [
        {
          stroke: '#475569',
          ticks: { stroke: '#334155', width: 1, size: 4 },
          grid: { stroke: '#1e293b', width: 1 },
          size: 28,
          font: '9px system-ui,sans-serif',
          values: (u, vals) =>
            vals.map((t) => {
              if (t == null) return '';
              const d = new Date(t * 1000);
              return `${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
            }),
        },
        {
          scale: 'y',
          stroke: '#64748b',
          ticks: { stroke: '#334155', width: 1, size: 4 },
          grid: { stroke: '#1e293b', width: 1 },
          size: 44,
          font: '9px system-ui,sans-serif',
        },
      ],
      series: [
        {},
        ...selected.map((s, i) => ({
          label: s.label,
          stroke: s.color,
          width: 1.5,
          fill: `${s.color}12`,
          points: { show: false },
          spanGaps: false,
          scale: scaleKey(i),
        })),
      ],
    };
  }

  function buildData(selected) {
    if (!selected.length) return [new Float64Array(0)];

    const minTime = nowSec - windowSec;

    // Find start index in the shared timeline
    let startIdx = 0;
    while (startIdx < timeline.length && timeline[startIdx] < minTime) startIdx++;

    const winSlice = timeline.slice(startIdx);

    if (winSlice.length === 0) {
      const now = nowSec || Date.now() / 1000;
      return [
        new Float64Array([now - windowSec, now]),
        ...selected.map(() => new Float64Array([NaN, NaN])),
      ];
    }

    const timeArr = Float64Array.from(winSlice);
    const valArrs = selected.map((s) => {
      // values[] is 1:1 aligned with timeline[]
      const sliced = s.values.slice(startIdx);
      const arr = new Float64Array(timeArr.length);
      for (let i = 0; i < arr.length; i++) {
        const v = sliced[i];
        arr[i] = v === null || v === undefined ? NaN : v;
      }
      return arr;
    });

    return [timeArr, ...valArrs];
  }

  // ── Plot lifecycle ────────────────────────────────────────────────────────────

  function rebuildPlot() {
    if (!containerEl) return;
    if (plot) { plot.destroy(); plot = null; }

    const selected = getSelectedSeries();
    const { w, h } = getSize();
    const data = buildData(selected);
    try {
      plot = new uPlot(buildOpts(selected, w, h), data, containerEl);
      const now = nowSec || Date.now() / 1000;
      plot.setScale('x', { min: now - windowSec, max: now });
    } catch (e) {
      console.warn('[DataGraph] uPlot init failed:', e);
      plot = null;
    }
  }

  function updateData() {
    if (!plot) return;
    const selected = getSelectedSeries();
    if (!selected.length) return;
    const data = buildData(selected);
    plot.setData(data);
    const now = nowSec || Date.now() / 1000;
    plot.setScale('x', { min: now - windowSec, max: now });
    // Update last-value display in the legend
    const lv = {};
    for (const s of selected) {
      for (let i = s.values.length - 1; i >= 0; i--) {
        if (s.values[i] !== null && s.values[i] !== undefined && isFinite(s.values[i])) {
          lv[s.key] = s.values[i];
          break;
        }
      }
    }
    lastValues = lv;
  }

  // New data arrived
  $: if (nowSec > 0 && mounted) updateData();
  // Window changed
  $: if (windowSec > 0 && mounted) updateData();

  let ro;

  onMount(() => {
    mounted = true;
    rebuildPlot();

    ro = new ResizeObserver(() => {
      if (!plot || !containerEl) return;
      const { w, h } = getSize();
      if (w < 10 || h < 10) return; // hidden tab — skip
      plot.setSize({ width: w, height: h });
    });
    ro.observe(containerEl);
  });

  onDestroy(() => {
    ro?.disconnect();
    plot?.destroy();
    plot = null;
  });
</script>

<div class="flex h-full bg-[#1e2129] rounded-lg border border-[#2e3340] overflow-hidden">

  <!-- ── Series selector sidebar ── -->
  <div class="w-48 flex-shrink-0 flex flex-col border-r border-[#2e3340] overflow-hidden">
    <div class="px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
      <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">{graphLabel}</span>
    </div>

    <div class="flex-1 overflow-y-auto min-h-0 p-1.5 space-y-px">
      {#if seriesKeys.length === 0}
        <p class="text-[11px] text-slate-700 italic px-2 py-2">No data yet</p>
      {:else}
        {#each seriesKeys as key (key)}
          {@const s = allSeries[key]}
          {@const checked = selectedKeys.has(key)}
          <label
            class="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer
                   hover:bg-[#252932] transition-colors select-none"
          >
            <input type="checkbox" {checked} class="sr-only" on:change={() => toggleSeries(key)} />

            <!-- Color swatch / checkbox -->
            <div
              class="w-3 h-3 rounded-sm flex-shrink-0 border transition-all flex items-center justify-center"
              style="background-color: {checked ? s.color : 'transparent'};
                     border-color: {checked ? s.color : '#475569'}"
            >
              {#if checked}
                <svg viewBox="0 0 10 10" fill="none" class="w-full h-full">
                  <polyline
                    points="1.5,5 4,7.5 8.5,2.5"
                    stroke="white"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              {/if}
            </div>

            <span class="text-[11px] truncate leading-tight {checked ? 'text-slate-200' : 'text-slate-500'}">
              {s.label}
            </span>
            {#if s.unit}
              <span class="text-[10px] text-slate-700 ml-auto flex-shrink-0 font-mono">{s.unit}</span>
            {/if}
          </label>
        {/each}
      {/if}
    </div>
  </div>

  <!-- ── Graph area ── -->
  <div class="flex-1 min-w-0 flex flex-col overflow-hidden">

    <!-- Legend -->
    {#if selectedKeys.size > 0}
      <div
        class="flex flex-wrap items-center gap-x-4 gap-y-0.5 px-3 py-1.5
               border-b border-[#2e3340] flex-shrink-0"
      >
        {#each [...selectedKeys].filter((k) => allSeries[k]) as key (key)}
          {@const s = allSeries[key]}
          {@const lv = lastValues[key]}
          <div class="flex items-center gap-1.5">
            <div class="w-5 h-0.5 rounded-full flex-shrink-0" style="background-color: {s.color}"></div>
            <span class="text-[10px] text-slate-400 whitespace-nowrap">{s.label}</span>
            {#if lv !== undefined}
              <span class="text-[10px] font-mono font-semibold text-slate-100 whitespace-nowrap">
                {Number.isInteger(lv) ? lv : lv.toFixed(2)}{s.unit ? ' ' + s.unit : ''}
              </span>
            {:else if s.unit}
              <span class="text-[10px] text-slate-600 whitespace-nowrap">({s.unit})</span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- uPlot container + empty-state overlay -->
    <div bind:this={containerEl} class="flex-1 min-h-0 relative bg-[#0f1117] overflow-hidden">
      {#if selectedKeys.size === 0}
        <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-700 pointer-events-none">
          <svg class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <polyline points="3,17 8,12 12,14 17,9 21,11" />
            <line x1="3" y1="20" x2="21" y2="20" />
          </svg>
          <span class="text-xs">Check series on the left to display</span>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  :global(.uplot) {
    display: block !important;
    width: 100% !important;
  }
</style>
