<script>
  import { connected, uptime } from '../lib/stores.js';

  /** Format uptime seconds → "H:MM:SS" or "MM:SS" */
  function formatUptime(secs) {
    if (secs === null || secs === undefined) return '--:--';
    const s = Math.floor(secs);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }
</script>

<header class="flex items-center gap-4 px-4 h-12 bg-[#1a1d26] border-b border-[#2e3340] flex-shrink-0">
  <!-- Logo / name -->
  <div class="flex items-center gap-2">
    <!-- Redwing icon: stylised "R" in a circle -->
    <svg class="w-7 h-7 text-red-500" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="14" cy="14" r="13" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5"/>
      <text x="14" y="19" text-anchor="middle" font-family="system-ui, sans-serif"
            font-size="13" font-weight="700" fill="currentColor">R</text>
    </svg>
    <span class="text-lg font-bold tracking-tight text-slate-100">Redwing</span>
  </div>

  <!-- Separator -->
  <div class="h-6 w-px bg-[#2e3340]"></div>

  <!-- Connection status -->
  <div class="flex items-center gap-2">
    <span
      class="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 transition-colors duration-300"
      class:bg-emerald-400={$connected}
      class:shadow-[0_0_6px_#34d399]={$connected}
      class:bg-red-500={!$connected}
    ></span>
    <span class="text-sm font-medium"
          class:text-emerald-400={$connected}
          class:text-red-400={!$connected}>
      {$connected ? 'Connected' : 'Disconnected'}
    </span>
  </div>

  <!-- Separator -->
  <div class="h-6 w-px bg-[#2e3340]"></div>

  <!-- Uptime -->
  <div class="flex items-center gap-1.5 text-sm text-slate-400">
    <svg class="w-4 h-4" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
      <path d="M8 4.5V8l2.5 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>
    <span class="font-mono tabular-nums">{formatUptime($uptime)}</span>
    <span class="text-slate-600">uptime</span>
  </div>

  <!-- Spacer -->
  <div class="flex-1"></div>

  <!-- Robot label -->
  <div class="text-xs text-slate-600 font-mono">
    ws://{location.host}/ws
  </div>
</header>
