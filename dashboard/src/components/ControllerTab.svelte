<script>
  import { onDestroy, onMount } from 'svelte';
  import { send }               from '../lib/ws.js';
  import { connected, cameraFrame, robotState } from '../lib/stores.js';
  import VirtualJoystick from './VirtualJoystick.svelte';
  import DPad            from './DPad.svelte';
  import FaceButtons     from './FaceButtons.svelte';
  import ShoulderButton  from './ShoulderButton.svelte';
  import LidarRadar      from './LidarRadar.svelte';

  // ── Center panel visibility ────────────────────────────────────────────
  let showCamera = true;
  let showLidar  = false;

  // ── LIDAR display config ───────────────────────────────────────────────
  let lidarOffset = 0;    // degrees
  let lidarMaxCm  = 400;  // cm
  let lidarCfgInit = false;

  // Sync local inputs from state once (or whenever dashboard is in control)
  $: {
    const cfg = $robotState?.lidar_config;
    if (cfg && !cfg.code_configured) {
      lidarOffset = cfg.offset  ?? 0;
      lidarMaxCm  = cfg.max_cm  ?? 400;
      lidarCfgInit = true;
    }
  }

  function sendLidarConfig() {
    send({ cmd: 'set_lidar_config', offset: Number(lidarOffset), max_cm: Number(lidarMaxCm) });
  }

  // ── Gamepad state ─────────────────────────────────────────────────────
  let lx = 0, ly = 0, rx = 0, ry = 0;
  let a = false, b = false, x = false, y = false;
  let up = false, down = false, left = false, right = false;
  let lb = false, rb = false, lt = 0, rt = 0;

  // ── Physical gamepad (Web Gamepad API) ────────────────────────────────
  let physicalIndex = null;
  let physicalName  = '';
  $: usingPhysical  = physicalIndex !== null;

  // refs to shoulder buttons so we can reset their latch on disconnect
  let lbBtn, ltBtn, rtBtn, rbBtn;

  const DEADZONE = 0.12;
  function applyDZ(v) {
    if (Math.abs(v) < DEADZONE) return 0;
    const s = v > 0 ? 1 : -1;
    return +(s * (Math.abs(v) - DEADZONE) / (1 - DEADZONE)).toFixed(3);
  }

  let pollRafId = null;

  function pollGamepad() {
    if (physicalIndex === null) return;
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    const gp = gamepads[physicalIndex];
    if (!gp) { pollRafId = requestAnimationFrame(pollGamepad); return; }

    lx = applyDZ(gp.axes[0] ?? 0);
    ly = applyDZ(-(gp.axes[1] ?? 0));
    rx = applyDZ(gp.axes[2] ?? 0);
    ry = applyDZ(-(gp.axes[3] ?? 0));

    a = gp.buttons[0]?.pressed ?? false;
    b = gp.buttons[1]?.pressed ?? false;
    x = gp.buttons[2]?.pressed ?? false;
    y = gp.buttons[3]?.pressed ?? false;
    lb = gp.buttons[4]?.pressed ?? false;
    rb = gp.buttons[5]?.pressed ?? false;
    lt = +(gp.buttons[6]?.value ?? 0).toFixed(3);
    rt = +(gp.buttons[7]?.value ?? 0).toFixed(3);

    // D-pad: standard buttons[12–15]; fallback to hat-switch axes[6/7]
    if (gp.buttons[12] !== undefined) {
      up    = gp.buttons[12]?.pressed ?? false;
      down  = gp.buttons[13]?.pressed ?? false;
      left  = gp.buttons[14]?.pressed ?? false;
      right = gp.buttons[15]?.pressed ?? false;
    } else {
      const hx = gp.axes[6] ?? 0;
      const hy = gp.axes[7] ?? 0;
      left  = hx < -0.5; right = hx > 0.5;
      up    = hy < -0.5; down  = hy > 0.5;
    }

    sendNow();
    pollRafId = requestAnimationFrame(pollGamepad);
  }

  function startPolling() {
    if (pollRafId !== null) return;
    pollRafId = requestAnimationFrame(pollGamepad);
  }
  function stopPolling() {
    if (pollRafId !== null) { cancelAnimationFrame(pollRafId); pollRafId = null; }
  }

  function handleConnected(e) {
    physicalIndex = e.gamepad.index;
    physicalName  = e.gamepad.id;
    startPolling();
  }

  function handleDisconnected(e) {
    if (e.gamepad.index !== physicalIndex) return;
    stopPolling();
    physicalIndex = null;
    physicalName  = '';
    // Reset shoulder button latch so virtual controls start fresh
    lbBtn?.reset(); ltBtn?.reset(); rtBtn?.reset(); rbBtn?.reset();
    sendZero();
  }

  onMount(() => {
    window.addEventListener('gamepadconnected',    handleConnected);
    window.addEventListener('gamepaddisconnected', handleDisconnected);
    // Pick up a gamepad that was already activated before this tab mounted
    if (navigator.getGamepads) {
      for (const gp of navigator.getGamepads()) {
        if (gp) { physicalIndex = gp.index; physicalName = gp.id; startPolling(); break; }
      }
    }
  });

  // ── RAF-throttled send (virtual controls) ────────────────────────────
  let rafId = null;
  let dirty = false;

  function markDirty() {
    if (dirty) return;
    dirty = true;
    rafId = requestAnimationFrame(() => { dirty = false; rafId = null; sendNow(); });
  }

  function sendNow() {
    send({ cmd: 'gamepad', lx, ly, rx, ry, a, b, x, y,
           up, down, left, right, lb, rb, lt, rt });
  }

  function sendZero() {
    stopPolling();
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; dirty = false; }
    lx = ly = rx = ry = lt = rt = 0;
    a = b = x = y = false;
    up = down = left = right = false;
    lb = rb = false;
    sendNow();
  }

  onDestroy(() => {
    window.removeEventListener('gamepadconnected',    handleConnected);
    window.removeEventListener('gamepaddisconnected', handleDisconnected);
    sendZero();
  });

  // ── Virtual input handlers (ignored when physical gamepad is active) ──
  function onLeftStick({ detail })   { if (usingPhysical) return; lx = detail.x; ly = detail.y; markDirty(); }
  function onRightStick({ detail })  { if (usingPhysical) return; rx = detail.x; ry = detail.y; markDirty(); }
  function onDPad({ detail })        { if (usingPhysical) return; up = detail.up; down = detail.down; left = detail.left; right = detail.right; markDirty(); }
  function onFaceButtons({ detail }) { if (usingPhysical) return; a = detail.a; b = detail.b; x = detail.x; y = detail.y; markDirty(); }
  function onLB({ detail }) { if (usingPhysical) return; lb = detail.active;            markDirty(); }
  function onRB({ detail }) { if (usingPhysical) return; rb = detail.active;            markDirty(); }
  function onLT({ detail }) { if (usingPhysical) return; lt = detail.active ? 1.0 : 0.0; markDirty(); }
  function onRT({ detail }) { if (usingPhysical) return; rt = detail.active ? 1.0 : 0.0; markDirty(); }
</script>

<div class="flex h-full bg-[#161920] text-slate-200 overflow-hidden select-none">

  <!-- ── Left column: L Shoulder / Left Stick / D-Pad ── -->
  <div class="flex flex-col items-center justify-start gap-6 pt-5 px-4"
       style="width: 200px; flex-shrink: 0;"
       style:opacity={usingPhysical ? 0.4 : 1}>

    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">L Shoulder</span>
      <div class="flex gap-3">
        <ShoulderButton label="LB" bind:this={lbBtn} on:change={onLB} />
        <ShoulderButton label="LT" bind:this={ltBtn} on:change={onLT} />
      </div>
    </div>

    <div class="flex flex-col items-center gap-2">
      <VirtualJoystick size={68} on:change={onLeftStick} />
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Left Stick</span>
    </div>

    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">D-Pad</span>
      <DPad on:change={onDPad} />
    </div>
  </div>

  <!-- ── Center: toggleable camera / LIDAR radar ── -->
  <div class="flex flex-col flex-1 min-w-0 items-center p-3 gap-2">

    <!-- Toggle buttons -->
    <div class="flex gap-2 flex-shrink-0">
      <!-- Camera toggle -->
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold
               border transition-all duration-100 select-none touch-none
               {showCamera
                 ? 'bg-blue-600/25 border-blue-500/60 text-blue-300'
                 : 'bg-[#1e2129] border-[#2e3340] text-slate-500 hover:text-slate-300'}"
        on:click={() => showCamera = !showCamera}
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="2" y="4" width="20" height="15" rx="2"/>
          <circle cx="12" cy="11.5" r="3.5"/>
        </svg>
        Camera
      </button>

      <!-- LIDAR toggle -->
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold
               border transition-all duration-100 select-none touch-none
               {showLidar
                 ? 'bg-green-600/25 border-green-500/60 text-green-300'
                 : 'bg-[#1e2129] border-[#2e3340] text-slate-500 hover:text-slate-300'}"
        on:click={() => showLidar = !showLidar}
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="3"/>
          <circle cx="12" cy="12" r="7"/>
          <line x1="12" y1="2" x2="12" y2="5"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
          <line x1="2" y1="12" x2="5" y2="12"/>
          <line x1="19" y1="12" x2="22" y2="12"/>
        </svg>
        LIDAR
      </button>
    </div>

    <!-- LIDAR settings row (visible when LIDAR panel is on) -->
    {#if showLidar}
      {@const codeLocked = $robotState?.lidar_config?.code_configured}
      <div class="flex flex-col gap-1.5 flex-shrink-0 w-full max-w-sm px-1"
           style:opacity={codeLocked ? 0.4 : 1}>

        <!-- Rotation -->
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-slate-500 uppercase tracking-widest w-14 flex-shrink-0">Rotation</span>
          <input
            type="range" min="-180" max="180" step="5"
            bind:value={lidarOffset}
            on:input={sendLidarConfig}
            disabled={codeLocked}
            class="flex-1 h-1.5 rounded-full appearance-none cursor-pointer accent-green-500
                   disabled:cursor-not-allowed"
            style="background: linear-gradient(to right,
              #16a34a {((lidarOffset + 180) / 360 * 100)}%,
              #2e3340 {((lidarOffset + 180) / 360 * 100)}%)"
          />
          <span class="text-[10px] font-mono text-green-400 w-10 text-right flex-shrink-0">
            {lidarOffset > 0 ? '+' : ''}{lidarOffset}°
          </span>
        </div>

        <!-- Max range -->
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-slate-500 uppercase tracking-widest w-14 flex-shrink-0">Max range</span>
          <input
            type="range" min="100" max="1200" step="50"
            bind:value={lidarMaxCm}
            on:input={sendLidarConfig}
            disabled={codeLocked}
            class="flex-1 h-1.5 rounded-full appearance-none cursor-pointer accent-green-500
                   disabled:cursor-not-allowed"
            style="background: linear-gradient(to right,
              #16a34a {((lidarMaxCm - 100) / 1100 * 100)}%,
              #2e3340 {((lidarMaxCm - 100) / 1100 * 100)}%)"
          />
          <span class="text-[10px] font-mono text-green-400 w-14 text-right flex-shrink-0">
            {lidarMaxCm} cm
          </span>
        </div>

        {#if codeLocked}
          <div class="text-[10px] text-slate-700 italic text-center">set by code</div>
        {/if}
      </div>
    {/if}

    {#if usingPhysical}
      <div class="text-[10px] text-blue-400 uppercase tracking-widest truncate max-w-full flex-shrink-0">
        🎮 {physicalName || 'Physical gamepad'}
      </div>
    {/if}

    <!-- Display area -->
    <div class="flex flex-1 min-h-0 w-full gap-2
                {showCamera && showLidar ? 'flex-row' : 'flex-col'}">

      {#if showCamera}
        <div class="flex-1 min-w-0 min-h-0 rounded-xl overflow-hidden border border-[#2e3340]"
             style="background:#000;">
          {#if $connected && $cameraFrame}
            <img
              src="data:image/jpeg;base64,{$cameraFrame}"
              alt="Robot camera"
              class="w-full h-full object-contain"
              draggable="false"
            />
          {:else}
            <div class="w-full h-full flex flex-col items-center justify-center gap-2 text-slate-600">
              <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none">
                <rect x="2" y="4" width="20" height="15" rx="2" stroke="currentColor" stroke-width="1.5"/>
                <circle cx="12" cy="11.5" r="3.5" stroke="currentColor" stroke-width="1.5"/>
                <circle cx="17.5" cy="6.5" r="1" fill="currentColor"/>
              </svg>
              <span class="text-xs">{$connected ? 'No camera signal' : 'Connecting…'}</span>
            </div>
          {/if}
        </div>
      {/if}

      {#if showLidar}
        <div class="flex-1 min-w-0 min-h-0 rounded-xl overflow-hidden border border-[#2e3340]">
          <LidarRadar />
        </div>
      {/if}

      {#if !showCamera && !showLidar}
        <div class="flex-1 flex items-center justify-center text-slate-700 text-xs">
          Enable a view above
        </div>
      {/if}

    </div>

    <div class="text-[10px] text-slate-600 uppercase tracking-widest flex-shrink-0">
      {usingPhysical ? 'Physical controller active' : 'Virtual Controller'}
    </div>
  </div>

  <!-- ── Right column: R Shoulder / Right Stick / ABXY ── -->
  <div class="flex flex-col items-center justify-start gap-6 pt-5 px-4"
       style="width: 200px; flex-shrink: 0;"
       style:opacity={usingPhysical ? 0.4 : 1}>

    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">R Shoulder</span>
      <div class="flex gap-3">
        <ShoulderButton label="RT" bind:this={rtBtn} on:change={onRT} />
        <ShoulderButton label="RB" bind:this={rbBtn} on:change={onRB} />
      </div>
    </div>

    <div class="flex flex-col items-center gap-2">
      <VirtualJoystick size={68} on:change={onRightStick} />
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Right Stick</span>
    </div>

    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Buttons</span>
      <FaceButtons on:change={onFaceButtons} />
    </div>
  </div>

</div>
