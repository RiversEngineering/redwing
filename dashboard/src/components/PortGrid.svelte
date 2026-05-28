<script>
  import { ports, activeTab, selectedPortId } from '../lib/stores.js';
  import PortCard from './PortCard.svelte';

  const SINGLE_PORTS = Array.from({ length: 8 }, (_, i) => ({ id: i,     label: `S${i}` }));
  const DUAL_PORTS   = Array.from({ length: 8 }, (_, i) => ({ id: i + 8, label: `D${i}` }));

  function openPort(id) {
    $selectedPortId = id;
    $activeTab = 'ports';
  }
</script>

<div class="flex flex-col bg-[#1e2129] rounded-lg border border-[#2e3340] overflow-hidden">
  <!-- Header -->
  <div class="flex items-center gap-2 px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 16 16" fill="none">
      <rect x="1.5" y="4" width="4" height="8" rx="1" stroke="currentColor" stroke-width="1.2"/>
      <rect x="6.5" y="4" width="4" height="8" rx="1" stroke="currentColor" stroke-width="1.2"/>
      <rect x="11.5" y="4" width="3" height="8" rx="1" stroke="currentColor" stroke-width="1.2"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Ports</span>
    <div class="ml-auto flex items-center gap-3 text-[10px] text-slate-600">
      <span class="flex items-center gap-1">
        <span class="w-1.5 h-3 rounded-sm bg-slate-500 inline-block"></span>
        Dual D0–D7
      </span>
      <span class="flex items-center gap-1">
        <span class="w-1.5 h-3 rounded-sm bg-slate-800 inline-block"></span>
        Single S0–S7
      </span>
    </div>
  </div>

  <!-- Dual-pin ports -->
  <div class="px-2 pt-2">
    <div class="text-[9px] text-slate-600 uppercase tracking-widest mb-1 px-0.5">Dual-pin</div>
    <div class="grid grid-cols-8 gap-1.5">
      {#each DUAL_PORTS as p}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div
          class="cursor-pointer rounded-lg transition-all duration-100
                 hover:ring-1 hover:ring-blue-500/50 hover:brightness-125"
          role="button"
          tabindex="0"
          title="Open {p.label} in Ports tab"
          on:click={() => openPort(p.id)}
          on:keydown={(e) => e.key === 'Enter' && openPort(p.id)}
        >
          <PortCard portId={p.id} portLabel={p.label} isDual={true} data={$ports[p.id]} />
        </div>
      {/each}
    </div>
  </div>

  <!-- Single-pin ports -->
  <div class="px-2 pt-2 pb-2">
    <div class="text-[9px] text-slate-600 uppercase tracking-widest mb-1 px-0.5">Single-pin</div>
    <div class="grid grid-cols-8 gap-1.5">
      {#each SINGLE_PORTS as p}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div
          class="cursor-pointer rounded-lg transition-all duration-100
                 hover:ring-1 hover:ring-blue-500/50 hover:brightness-125"
          role="button"
          tabindex="0"
          title="Open {p.label} in Ports tab"
          on:click={() => openPort(p.id)}
          on:keydown={(e) => e.key === 'Enter' && openPort(p.id)}
        >
          <PortCard portId={p.id} portLabel={p.label} isDual={false} data={$ports[p.id]} />
        </div>
      {/each}
    </div>
  </div>
</div>
