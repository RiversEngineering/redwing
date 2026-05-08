<script>
  /**
   * GraphSeries – a single uPlot rolling-window graph.
   *
   * Props:
   *   label     {string}    display title
   *   unit      {string}    y-axis unit label
   *   color     {string}    hex colour for the line
   *   times     {number[]}  Unix seconds (shared array reference from GraphPanel)
   *   values    {number[]}  corresponding y values
   *   windowSec {number}    rolling window size in seconds
   *   tick      {number}    increment each time parent pushes new data — triggers update
   */
  export let label;
  export let unit;
  export let color;
  export let times;
  export let values;
  export let windowSec = 30;
  export let tick = 0;

  import { onMount, onDestroy } from 'svelte';
  import uPlot from 'uplot';

  let containerEl;
  let plot = null;

  function buildOptions(w, h) {
    return {
      title: `${label} (${unit})`,
      width: w,
      height: h,
      cursor: { show: false },
      select: { show: false },
      legend: { show: false },
      padding: [4, 4, 0, 0],
      scales: {
        x: { time: true },
        y: { auto: true },
      },
      axes: [
        {
          // x axis (time)
          stroke: '#475569',
          ticks: { stroke: '#334155', width: 1, size: 4 },
          grid:  { stroke: '#1e293b', width: 1 },
          size: 28,
          font: '9px system-ui,sans-serif',
          values: (u, vals) =>
            vals.map((t) => {
              if (t == null) return '';
              const d = new Date(t * 1000);
              return `${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
            }),
        },
        {
          // y axis
          stroke: '#64748b',
          ticks: { stroke: '#334155', width: 1, size: 4 },
          grid:  { stroke: '#1e293b', width: 1 },
          size: 36,
          font: '9px system-ui,sans-serif',
        },
      ],
      series: [
        {},
        {
          stroke: color,
          width: 1.5,
          fill: `${color}1a`,
          points: { show: false },
        },
      ],
    };
  }

  function getSize() {
    if (!containerEl) return { w: 280, h: 90 };
    return {
      w: containerEl.clientWidth  || 280,
      h: containerEl.clientHeight || 90,
    };
  }

  function updatePlot() {
    if (!plot) return;
    const ts = times.length > 0 ? Float64Array.from(times) : new Float64Array(0);
    const vs = values.length > 0 ? Float64Array.from(values) : new Float64Array(0);
    plot.setData([ts, vs]);
    if (ts.length > 0) {
      const nowSec = ts[ts.length - 1];
      plot.setScale('x', { min: nowSec - windowSec, max: nowSec });
    }
  }

  // Resize observer to handle container size changes
  let ro;

  onMount(() => {
    const { w, h } = getSize();
    plot = new uPlot(buildOptions(w, h), [new Float64Array(0), new Float64Array(0)], containerEl);

    ro = new ResizeObserver(() => {
      if (!plot || !containerEl) return;
      const { w: nw, h: nh } = getSize();
      plot.setSize({ width: nw, height: nh });
    });
    ro.observe(containerEl);

    // Render initial data (may already have buffered points)
    updatePlot();
  });

  onDestroy(() => {
    ro?.disconnect();
    plot?.destroy();
    plot = null;
  });

  // React to new data whenever `tick` changes
  $: if (tick !== undefined && plot) {
    updatePlot();
  }
</script>

<!-- The uPlot instance mounts directly into this div -->
<div
  bind:this={containerEl}
  class="w-full h-full rounded overflow-hidden bg-[#0f1117]"
></div>

<style>
  :global(.uplot) {
    width: 100% !important;
  }
  :global(.u-title) {
    font-size: 10px !important;
    color: #94a3b8 !important;
    padding: 2px 0 !important;
  }
</style>
