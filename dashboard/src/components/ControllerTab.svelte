<script>
  import { onDestroy } from 'svelte';
  import { send } from '../lib/ws.js';
  import { connected, cameraFrame } from '../lib/stores.js';
  import VirtualJoystick from './VirtualJoystick.svelte';
  import DPad           from './DPad.svelte';
  import FaceButtons    from './FaceButtons.svelte';

  // Current gamepad state — sent to daemon on any change
  let lx = 0, ly = 0, rx = 0, ry = 0;
  let a = false, b = false, x = false, y = false;
  let up = false, down = false, left = false, right = false;

  // Throttled send: max one packet per animation frame (~60 fps on iPad)
  let rafId = null;
  let dirty = false;

  function markDirty() {
    if (dirty) return;
    dirty = true;
    rafId = requestAnimationFrame(() => {
      dirty = false;
      rafId = null;
      sendNow();
    });
  }

  function sendNow() {
    send({ cmd: 'gamepad', lx, ly, rx, ry, a, b, x, y, up, down, left, right });
  }

  function sendZero() {
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; dirty = false; }
    lx = ly = rx = ry = 0;
    a = b = x = y = false;
    up = down = left = right = false;
    sendNow();
  }

  // Reset all inputs to zero when this tab is unmounted or hidden
  onDestroy(sendZero);

  // --- Input handlers ---

  function onLeftStick({ detail }) {
    lx = detail.x; ly = detail.y;
    markDirty();
  }

  function onRightStick({ detail }) {
    rx = detail.x; ry = detail.y;
    markDirty();
  }

  function onDPad({ detail }) {
    up = detail.up; down = detail.down; left = detail.left; right = detail.right;
    markDirty();
  }

  function onFaceButtons({ detail }) {
    a = detail.a; b = detail.b; x = detail.x; y = detail.y;
    markDirty();
  }
</script>

<div class="flex h-full bg-[#161920] text-slate-200 overflow-hidden select-none">

  <!-- ── Left column: D-pad (top) + left joystick (bottom) ── -->
  <div class="flex flex-col items-center justify-center py-6 px-4 gap-6"
       style="width: 220px; flex-shrink: 0;">
    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">D-Pad</span>
      <DPad on:change={onDPad} />
    </div>
    <div class="flex flex-col items-center gap-2">
      <VirtualJoystick size={72} on:change={onLeftStick} />
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Left Stick</span>
    </div>
  </div>

  <!-- ── Center: camera feed ── -->
  <div class="flex flex-col flex-1 min-w-0 items-center justify-center p-3 gap-2">
    <div class="w-full flex-1 min-h-0 rounded-xl overflow-hidden border border-[#2e3340]"
         style="background:#000;">
      {#if $connected && $cameraFrame}
        <img
          src="data:image/jpeg;base64,{$cameraFrame}"
          alt="Robot camera"
          class="w-full h-full object-contain"
          draggable="false"
        />
      {:else}
        <div class="w-full h-full flex flex-col items-center justify-center gap-3 text-slate-600">
          <svg class="w-16 h-16" viewBox="0 0 24 24" fill="none">
            <rect x="2" y="4" width="20" height="15" rx="2" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="12" cy="11.5" r="3.5" stroke="currentColor" stroke-width="1.5"/>
            <circle cx="17.5" cy="6.5" r="1" fill="currentColor"/>
          </svg>
          <span class="text-sm font-medium">
            {$connected ? 'No camera signal' : 'Connecting…'}
          </span>
        </div>
      {/if}
    </div>

    <!-- Source indicator -->
    <div class="text-[10px] text-slate-600 uppercase tracking-widest">
      Virtual Controller
    </div>
  </div>

  <!-- ── Right column: ABXY (top) + right joystick (bottom) ── -->
  <div class="flex flex-col items-center justify-center py-6 px-4 gap-6"
       style="width: 220px; flex-shrink: 0;">
    <div class="flex flex-col items-center gap-2">
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Buttons</span>
      <FaceButtons on:change={onFaceButtons} />
    </div>
    <div class="flex flex-col items-center gap-2">
      <VirtualJoystick size={72} on:change={onRightStick} />
      <span class="text-[10px] text-slate-500 uppercase tracking-widest">Right Stick</span>
    </div>
  </div>

</div>
