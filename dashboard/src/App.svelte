<script>
  import { onDestroy } from 'svelte';
  import { subscribe, onStatus } from './lib/ws.js';
  import { connected, robotState, pushLog, cameraFrame } from './lib/stores.js';

  import TopBar      from './components/TopBar.svelte';
  import CameraPanel from './components/CameraPanel.svelte';
  import PortGrid    from './components/PortGrid.svelte';
  import GraphPanel  from './components/GraphPanel.svelte';
  import DebugConsole from './components/DebugConsole.svelte';
  import DataTab     from './components/DataTab.svelte';
  import PortsTab    from './components/PortsTab.svelte';

  let activeTab = 'overview';

  // Sync connection status into the store
  const unsubStatus = onStatus((v) => connected.set(v));

  // Route incoming WebSocket messages to the correct store
  const unsubWs = subscribe((msg) => {
    if (msg.type === 'state') {
      robotState.set(msg);
    } else if (msg.type === 'log') {
      pushLog({ level: msg.level, message: msg.message, ts: msg.ts });
    } else if (msg.type === 'frame') {
      cameraFrame.set(msg.data);
    }
  });

  onDestroy(() => {
    unsubStatus();
    unsubWs();
  });

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'ports',    label: 'Ports' },
    { id: 'data',     label: 'Data' },
  ];
</script>

<div class="flex flex-col h-screen bg-[#161920] text-slate-200 overflow-hidden">

  <!-- Top bar -->
  <TopBar />

  <!-- Tab bar -->
  <div class="flex items-end gap-0 px-2 border-b border-[#2e3340] bg-[#1a1d26] flex-shrink-0">
    {#each TABS as tab}
      <button
        class="px-4 py-2 text-xs font-semibold uppercase tracking-widest transition-colors
               border-b-2 -mb-px
               {activeTab === tab.id
                 ? 'border-blue-500 text-blue-400 bg-[#161920]'
                 : 'border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-600'}"
        on:click={() => (activeTab = tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </div>

  <!-- Tab content — both always mounted so data accumulates off-screen -->

  <!-- Overview tab -->
  <div
    class="flex flex-1 min-h-0 gap-2 p-2"
    style="display: {activeTab === 'overview' ? 'flex' : 'none'}"
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
    style="display: {activeTab === 'ports' ? 'flex' : 'none'}; flex-direction: column;"
  >
    <PortsTab />
  </div>

  <!-- Data tab -->
  <div
    class="flex-1 min-h-0 overflow-hidden"
    style="display: {activeTab === 'data' ? 'flex' : 'none'}; flex-direction: column;"
  >
    <DataTab />
  </div>

</div>
