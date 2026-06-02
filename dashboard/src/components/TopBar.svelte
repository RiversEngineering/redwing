<script>
  import { connected, uptime, robotState } from '../lib/stores.js';

  function formatUptime(secs) {
    if (secs === null || secs === undefined) return '--:--';
    const s = Math.floor(secs);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  }

  $: battery = $robotState?.battery ?? null;
  $: soc     = battery?.soc     ?? 0;
  $: voltage = battery?.voltage ?? 0;

  // Fill level: 0–4 bars (each bar = 25%)
  $: bars = battery ? Math.round(soc / 25) : 0;

  $: battColor = !battery    ? 'text-slate-700'
               : soc > 50   ? 'text-emerald-400'
               : soc > 20   ? 'text-amber-400'
               :               'text-red-400';
</script>

<header class="flex items-center gap-4 px-4 h-12 bg-[#1a1d26] border-b border-[#2e3340] flex-shrink-0">
  <!-- Logo -->
  <div class="flex items-center gap-2">
    <svg class="w-7 h-7 text-red-500" viewBox="0 0 28 28" fill="none">
      <circle cx="14" cy="14" r="13" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5"/>
      <text x="14" y="19" text-anchor="middle" font-family="system-ui, sans-serif"
            font-size="13" font-weight="700" fill="currentColor">R</text>
    </svg>
    <span class="text-lg font-bold tracking-tight text-slate-100">Redwing</span>
  </div>

  <div class="h-6 w-px bg-[#2e3340]"></div>

  <!-- Connection -->
  <div class="flex items-center gap-2">
    <span class="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 transition-colors duration-300"
          class:bg-emerald-400={$connected} class:shadow-[0_0_6px_#34d399]={$connected}
          class:bg-red-500={!$connected}></span>
    <span class="text-sm font-medium"
          class:text-emerald-400={$connected} class:text-red-400={!$connected}>
      {$connected ? 'Connected' : 'Disconnected'}
    </span>
  </div>

  <div class="h-6 w-px bg-[#2e3340]"></div>

  <!-- Uptime -->
  <div class="flex items-center gap-1.5 text-sm text-slate-400">
    <svg class="w-4 h-4" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
      <path d="M8 4.5V8l2.5 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>
    <span class="font-mono tabular-nums">{formatUptime($uptime)}</span>
    <span class="text-slate-600">uptime</span>
  </div>

  <div class="flex-1"></div>

  <!-- Battery (only shown when fuel gauge is present) -->
  {#if battery}
    <div class="flex items-center gap-1.5 {battColor}" title="{voltage.toFixed(3)} V">

      <!-- Battery icon -->
      <svg class="w-6 h-4" viewBox="0 0 24 14" fill="none">
        <!-- Outer body -->
        <rect x="0.75" y="0.75" width="20.5" height="12.5" rx="2" stroke="currentColor" stroke-width="1.5"/>
        <!-- Terminal nub -->
        <rect x="21.5" y="4" width="2" height="6" rx="0.75" fill="currentColor" opacity="0.6"/>
        <!-- Fill bars (each ≈ 4.5 px wide with 1 px gap, inside 2 px padding) -->
        {#each [0,1,2,3] as b}
          <rect
            x={2.5 + b * 4.75}
            y="2.5"
            width="3.75"
            height="9"
            rx="0.75"
            fill="currentColor"
            opacity={b < bars ? 1 : 0.12}
          />
        {/each}
      </svg>

      <!-- Percentage -->
      <span class="text-sm font-semibold tabular-nums">{soc.toFixed(0)}%</span>

      <!-- Voltage (small) -->
      <span class="text-[11px] tabular-nums text-slate-500">{voltage.toFixed(2)}V</span>
    </div>

    <div class="h-6 w-px bg-[#2e3340]"></div>
  {/if}

  <div class="text-xs text-slate-600 font-mono">
    ws://{location.host}/ws
  </div>
</header>
