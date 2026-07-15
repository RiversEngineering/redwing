<script>
  import { onDestroy, afterUpdate } from 'svelte';
  import { logs, clearLogs } from '../lib/stores.js';

  let scrollEl;
  let autoScroll = true;
  let prevLogCount = 0;

  // After each update, scroll to bottom if autoScroll is enabled
  afterUpdate(() => {
    if (!scrollEl) return;
    const newCount = $logs.length;
    if (autoScroll && newCount !== prevLogCount) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
    prevLogCount = newCount;
  });

  function handleScroll() {
    if (!scrollEl) return;
    const threshold = 40; // px from bottom
    const atBottom = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < threshold;
    autoScroll = atBottom;
  }

  function formatTs(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    const ms = String(d.getMilliseconds()).padStart(3, '0');
    return `${hh}:${mm}:${ss}.${ms}`;
  }

  function levelClass(level) {
    switch (level?.toLowerCase()) {
      case 'error': return 'text-red-400';
      case 'warn':
      case 'warning': return 'text-yellow-400';
      case 'debug': return 'text-slate-500';
      default: return 'text-slate-300';
    }
  }

  function levelBadge(level) {
    switch (level?.toLowerCase()) {
      case 'error':   return 'bg-red-900/60 text-red-300';
      case 'warn':
      case 'warning': return 'bg-yellow-900/60 text-yellow-300';
      case 'debug':   return 'bg-slate-800 text-slate-500';
      default:        return 'bg-slate-800 text-slate-400';
    }
  }
</script>

<div class="flex flex-col h-full bg-[#1a1d26] rounded-lg border border-[#2e3340] overflow-hidden">
  <!-- Header -->
  <div class="flex items-center gap-2 px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1.5" y="1.5" width="13" height="13" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
      <path d="M4 5.5h8M4 8h5M4 10.5h6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Debug Console</span>

    <!-- Auto-scroll indicator -->
    <button
      on:click={() => { autoScroll = !autoScroll; if (autoScroll && scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight; }}
      class="ml-auto flex items-center gap-1.5 text-[10px] px-2 py-0.5 rounded border transition-colors
             {autoScroll
               ? 'border-emerald-700 text-emerald-400 bg-emerald-900/30'
               : 'border-slate-700 text-slate-500 bg-transparent'}"
      title="Toggle auto-scroll"
    >
      <svg class="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round">
        <line x1="6" y1="1" x2="6" y2="9"/>
        <polyline points="3,7 6,10 9,7"/>
      </svg>
      {autoScroll ? 'Auto' : 'Paused'}
    </button>

    <!-- Log count -->
    <span class="text-[10px] text-slate-600 font-mono">{$logs.length}/200</span>

    <!-- Clear button -->
    <button
      on:click={clearLogs}
      class="text-[10px] px-2 py-0.5 rounded border border-slate-700 text-slate-500
             hover:border-slate-500 hover:text-slate-300 active:bg-slate-800 transition-colors"
    >
      Clear
    </button>
  </div>

  <!-- Log output -->
  <div
    bind:this={scrollEl}
    on:scroll={handleScroll}
    class="flex-1 overflow-y-auto min-h-0 font-mono text-xs"
  >
    {#if $logs.length === 0}
      <div class="flex items-center justify-center h-full text-slate-700 text-sm italic">
        No log messages yet
      </div>
    {:else}
      <table class="w-full border-collapse">
        <tbody>
          {#each $logs as entry (entry.id)}
            <tr class="hover:bg-white/[0.02] border-b border-[#1e2130]/50">
              <!-- Timestamp -->
              <td class="text-slate-600 px-3 py-0.5 whitespace-nowrap align-top w-28">
                {formatTs(entry.ts)}
              </td>
              <!-- Level badge -->
              <td class="px-2 py-0.5 align-top w-14">
                <span class="inline-block text-[9px] font-bold uppercase px-1.5 py-0.5 rounded
                             {levelBadge(entry.level)}">
                  {entry.level?.toUpperCase().slice(0,4) ?? 'INFO'}
                </span>
              </td>
              <!-- Message -->
              <td class="px-2 py-0.5 align-top {levelClass(entry.level)} whitespace-pre-wrap break-words">
                {entry.message}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>
