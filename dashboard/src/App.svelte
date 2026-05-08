<script>
  import { onDestroy } from 'svelte';
  import { subscribe, onStatus } from './lib/ws.js';
  import { connected, robotState, pushLog } from './lib/stores.js';

  import TopBar from './components/TopBar.svelte';
  import CameraPanel from './components/CameraPanel.svelte';
  import PortGrid from './components/PortGrid.svelte';
  import GraphPanel from './components/GraphPanel.svelte';
  import DebugConsole from './components/DebugConsole.svelte';

  // Sync connection status into the store
  const unsubStatus = onStatus((v) => connected.set(v));

  // Route incoming WebSocket messages to the correct store
  const unsubWs = subscribe((msg) => {
    if (msg.type === 'state') {
      robotState.set(msg);
    } else if (msg.type === 'log') {
      pushLog({ level: msg.level, message: msg.message, ts: msg.ts });
    }
  });

  onDestroy(() => {
    unsubStatus();
    unsubWs();
  });
</script>

<div class="flex flex-col h-screen bg-[#161920] text-slate-200 overflow-hidden">
  <!-- Top bar: fixed height -->
  <TopBar />

  <!-- Main content area: fills remaining space -->
  <div class="flex flex-1 min-h-0 gap-2 p-2">

    <!-- Left column: Camera (tall, fixed-ish width) -->
    <div class="flex flex-col w-64 flex-shrink-0 gap-2">
      <CameraPanel />
    </div>

    <!-- Center + Right: port grid, graphs, console stacked -->
    <div class="flex flex-col flex-1 min-w-0 gap-2">

      <!-- Upper row: ports and graphs side by side -->
      <div class="flex flex-1 min-h-0 gap-2">
        <!-- Port grid -->
        <div class="flex-1 min-w-0">
          <PortGrid />
        </div>

        <!-- Graphs -->
        <div class="w-80 flex-shrink-0">
          <GraphPanel />
        </div>
      </div>

      <!-- Debug console: fixed bottom height -->
      <div class="h-48 flex-shrink-0">
        <DebugConsole />
      </div>

    </div>
  </div>
</div>
