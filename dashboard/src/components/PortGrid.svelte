<script>
  import { ports, robotState, activeTab, selectedPortId, selectedPcaChannelId } from '../lib/stores.js';
  import PortCard from './PortCard.svelte';
  import MiniPortCard from './MiniPortCard.svelte';

  const SINGLE_PORTS  = Array.from({ length: 8 },  (_, i) => ({ id: i,     label: `S${i}` }));
  const DUAL_PORTS    = Array.from({ length: 8 },  (_, i) => ({ id: i + 8, label: `D${i}` }));
  const PCA_CHANNELS  = Array.from({ length: 16 }, (_, i) => ({ id: i,     label: `P${i}` }));

  function openPort(id) {
    $selectedPortId = id;
    $activeTab = 'ports';
  }

  function openPcaChannel(id) {
    $selectedPcaChannelId = id;
    $activeTab = 'ports';
  }

  // Port 16's dedicated I²C slot only earns a card when a specific sensor
  // (e.g. VL53L0X) was recognized — type 'i2c' means "something answered
  // the bus scan but wasn't identified," which isn't worth surfacing here.
  $: hasI2cSensor = $ports[16] && $ports[16].type !== 'i2c';
  $: pcaState = $robotState?.pca9685 ?? { present: false, channels: {} };
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

  <!-- Single-pin ports -->
  <div class="px-2 pt-2">
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

  <!-- I²C bus: dedicated sensor port, IMU, and PCA9685 expansion channels — -->
  <!-- one dense row, each only shown when actually present/detected.       -->
  {#if hasI2cSensor || $ports[17] || pcaState.present}
    <div class="px-2 pt-2 pb-2">
      <div class="text-[9px] text-slate-600 uppercase tracking-widest mb-1 px-0.5">I²C</div>
      <div class="flex flex-wrap items-stretch gap-1.5">
        {#if hasI2cSensor}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="cursor-pointer rounded-lg transition-all duration-100 w-[calc(12.5%-6px)]
                   hover:ring-1 hover:ring-teal-500/50 hover:brightness-125"
            role="button"
            tabindex="0"
            title="Open I²C port in Ports tab"
            on:click={() => openPort(16)}
            on:keydown={(e) => e.key === 'Enter' && openPort(16)}
          >
            <PortCard portId={16} portLabel="I²C" isDual={true} data={$ports[16]} />
          </div>
        {/if}

        {#if $ports[17]}
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="cursor-pointer rounded-lg transition-all duration-100 w-[calc(12.5%-6px)]
                   hover:ring-1 hover:ring-indigo-500/50 hover:brightness-125"
            role="button"
            tabindex="0"
            title="Open IMU in Ports tab"
            on:click={() => openPort(17)}
            on:keydown={(e) => e.key === 'Enter' && openPort(17)}
          >
            <PortCard portId={17} portLabel="IMU" isDual={true} data={$ports[17]} />
          </div>
        {/if}

        {#if pcaState.present}
          <!-- Two rows of 8, filling column-by-column, so all 16 channels sit -->
          <!-- next to I²C/IMU instead of wrapping into a row of their own.    -->
          <div class="grid grid-rows-2 grid-flow-col auto-cols-[3.75rem] gap-1">
            {#each PCA_CHANNELS as ch}
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <div
                class="cursor-pointer rounded-md transition-all duration-100
                       hover:ring-1 hover:ring-purple-500/50 hover:brightness-125"
                role="button"
                tabindex="0"
                title="Open {ch.label} in Ports tab"
                on:click={() => openPcaChannel(ch.id)}
                on:keydown={(e) => e.key === 'Enter' && openPcaChannel(ch.id)}
              >
                <MiniPortCard
                  label={ch.label}
                  data={pcaState.channels?.[String(ch.id)]}
                  badgeClass="bg-purple-900/40 text-purple-400"
                />
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
