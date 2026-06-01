<script>
  import { onDestroy } from 'svelte';
  import { subscribe, onStatus, send } from './lib/ws.js';
  import { connected, robotState, pushLog, cameraFrame, activeTab, pushPlot } from './lib/stores.js';

  import TopBar        from './components/TopBar.svelte';
  import CameraPanel   from './components/CameraPanel.svelte';
  import PortGrid      from './components/PortGrid.svelte';
  import GraphPanel    from './components/GraphPanel.svelte';
  import DebugConsole  from './components/DebugConsole.svelte';
  import DataTab       from './components/DataTab.svelte';
  import PortsTab      from './components/PortsTab.svelte';
  import ControllerTab from './components/ControllerTab.svelte';

  // When navigating away from the controller tab, zero out gamepad state.
  // ControllerTab's onDestroy also sends zero, but this fires first.
  function setTab(id) {
    if ($activeTab === 'controller' && id !== 'controller') {
      send({ cmd: 'gamepad',
             lx: 0, ly: 0, rx: 0, ry: 0,
             a: false, b: false, x: false, y: false,
             up: false, down: false, left: false, right: false,
             lb: false, rb: false, lt: 0, rt: 0 });
    }
    $activeTab = id;
  }

  // Sync connection status into the store
  const unsubStatus = onStatus((v) => connected.set(v));

  // Route incoming WebSocket messages to the correct store
  const unsubWs = subscribe((msg) => {
    if (msg.type === 'state') {
      robotState.set(msg);
    } else if (msg.type === 'log') {
      pushLog({ level: msg.level, message: msg.message, ts: msg.ts });
    } else if (msg.type === 'plot') {
      pushPlot(msg.label, msg.value, msg.ts);
    } else if (msg.type === 'frame') {
      cameraFrame.set(msg.data);
    }
  });

  onDestroy(() => {
    unsubStatus();
    unsubWs();
  });

  const tabs = [
    { id: 'overview',    label: 'Overview' },
    { id: 'ports',       label: 'Ports' },
    { id: 'data',        label: 'Data' },
    { id: 'controller',  label: 'Controller' },
  ];
</script>

<div class="flex flex-col h-screen bg-[#161920] text-slate-200 overflow-hidden">

  <!-- Top bar -->
  <TopBar />

  <!-- Tab bar -->
  <div class="flex items-end gap-0 px-2 border-b border-[#2e3340] bg-[#1a1d26] flex-shrink-0">
    {#each tabs as tab}
      <button
        class="px-4 py-2 text-xs font-semibold uppercase tracking-widest transition-colors
               border-b-2 -mb-px
               {$activeTab === tab.id
                 ? 'border-blue-500 text-blue-400 bg-[#161920]'
                 : 'border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-600'}"
        on:click={() => setTab(tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </div>

  <!-- Tab content — both always mounted so data accumulates off-screen -->

  <!-- Overview tab -->
  <div
    class="flex flex-1 min-h-0 gap-2 p-2"
    style="display: {$activeTab === 'overview' ? 'flex' : 'none'}"
  >
    <!-- Left column: camera + graph stacked, wider -->
    <div class="w-80 flex-shrink-0 flex flex-col gap-2">
      <div class="h-52 flex-shrink-0">
        <CameraPanel />
      </div>
      <div class="flex-1 min-h-0">
        <GraphPanel />
      </div>
    </div>

    <!-- Right column: ports (natural height) + debug console (fills rest) -->
    <div class="flex flex-col flex-1 min-w-0 gap-2">
      <div class="flex-shrink-0">
        <PortGrid />
      </div>
      <div class="flex-1 min-h-0">
        <DebugConsole />
      </div>
    </div>
  </div>

  <!-- Ports tab -->
  <div
    class="flex-1 min-h-0 overflow-hidden"
    style="display: {$activeTab === 'ports' ? 'flex' : 'none'}; flex-direction: column;"
  >
    <PortsTab />
  </div>

  <!-- Data tab -->
  <div
    class="flex-1 min-h-0 overflow-hidden"
    style="display: {$activeTab === 'data' ? 'flex' : 'none'}; flex-direction: column;"
  >
    <DataTab />
  </div>

  <!-- Controller tab — mounted only while active so onDestroy zeroes gamepad on switch -->
  {#if $activeTab === 'controller'}
    <div class="flex-1 min-h-0 overflow-hidden flex flex-col">
      <ControllerTab />
    </div>
  {/if}

</div>
