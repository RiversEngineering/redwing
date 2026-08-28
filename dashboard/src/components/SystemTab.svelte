<script>
  import { send } from '../lib/ws.js';
  import { connected, flashStatus, robotState } from '../lib/stores.js';

  // ── Camera resolution / frame rate (runtime-only — see daemon/camera.py) ──
  // Both are native discrete modes on this camera (confirmed via v4l2-ctl) —
  // named by height, the standard "240p"/"480p" convention.
  const CAMERA_RESOLUTIONS = [[320, 240, '240p', '320×240'], [640, 480, '480p', '640×480']];
  const CAMERA_FPS_OPTIONS = [30, 60];

  $: cameraConfig = $robotState?.camera?.config ?? { width: 640, height: 480, fps: 30, actual_width: null, actual_height: null };
  $: cameraActualFps = $robotState?.camera?.actual_fps ?? null;

  function setCameraResolution(width, height) {
    send({ cmd: 'set_camera_config', width, height, fps: cameraConfig.fps ?? 30 });
  }

  function setCameraFps(fps) {
    send({ cmd: 'set_camera_config', width: cameraConfig.width ?? 640, height: cameraConfig.height ?? 480, fps });
  }

  // Confirmation state — null | 'shutdown' | 'reboot'
  let confirming = null;
  let shutdownSent = false;

  function requestAction(action) {
    confirming = action;
  }

  function cancel() {
    confirming = null;
  }

  function confirm() {
    if (!confirming) return;
    shutdownSent = true;
    send({ cmd: 'system_power', action: confirming });
    confirming = null;
  }

  // Firmware flash confirmation — separate from the power confirm above so
  // flashing doesn't interrupt/replace the whole page the way shutdown does.
  let firmwareConfirming = false;

  function requestFlash() {
    firmwareConfirming = true;
  }

  function cancelFlash() {
    firmwareConfirming = false;
  }

  function confirmFlash() {
    firmwareConfirming = false;
    send({ cmd: 'flash_firmware' });
  }
</script>

<div class="flex flex-col h-full bg-[#161920] text-slate-200">

  <!-- Header -->
  <div class="flex items-center gap-2 px-4 py-2 border-b border-[#2e3340] bg-[#1a1d26] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">System</span>
  </div>

  <!-- Content -->
  <div class="flex-1 flex items-start justify-center p-8 overflow-y-auto">
    <div class="max-w-md w-full space-y-8">

      {#if shutdownSent}
        <!-- Sent state -->
        <div class="flex flex-col items-center gap-4 text-center py-12">
          <svg class="w-16 h-16 text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M12 2v10M6.34 6.34a8 8 0 1 0 11.32 0"/>
          </svg>
          <p class="text-slate-400 font-semibold">Command sent.</p>
          <p class="text-slate-600 text-sm">The Pi is shutting down. This page will stop responding shortly.</p>
        </div>

      {:else if confirming}
        <!-- Confirmation step -->
        <div class="bg-[#1e2129] rounded-xl border border-red-700/40 p-6 space-y-4">
          <div class="flex items-center gap-3">
            <svg class="w-6 h-6 text-red-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <p class="text-sm font-semibold text-slate-200">
              {confirming === 'shutdown' ? 'Shut down the Raspberry Pi?' : 'Restart the Raspberry Pi?'}
            </p>
          </div>
          <p class="text-xs text-slate-500">
            {confirming === 'shutdown'
              ? 'The Pi will power off immediately. You will need to physically unplug and replug it to turn it back on.'
              : 'The Pi will restart. The dashboard will be unreachable for about 30 seconds.'}
          </p>
          <div class="flex gap-3 pt-1">
            <button
              class="flex-1 py-2.5 rounded-lg text-sm font-bold bg-red-700/30 border border-red-600/60
                     text-red-300 hover:bg-red-700/50 transition-colors"
              on:click={confirm}
            >
              {confirming === 'shutdown' ? 'Yes, shut down' : 'Yes, restart'}
            </button>
            <button
              class="px-5 py-2.5 rounded-lg text-sm text-slate-400 border border-[#2e3340]
                     hover:text-slate-200 hover:border-slate-500 transition-colors"
              on:click={cancel}
            >
              Cancel
            </button>
          </div>
        </div>

      {:else}
        <!-- Normal state -->
        <div class="space-y-3">
          <p class="text-xs text-slate-600 uppercase tracking-widest">Power</p>

          <!-- Shut down -->
          <div class="bg-[#1e2129] rounded-xl border border-[#2e3340] p-5 flex items-center gap-4">
            <div class="flex-1">
              <p class="text-sm font-semibold text-slate-200">Shut down</p>
              <p class="text-xs text-slate-600 mt-0.5">
                Powers off the Raspberry Pi. Must be physically unplugged and replugged to restart.
              </p>
            </div>
            <button
              disabled={!$connected}
              class="px-4 py-2 rounded-lg text-sm font-semibold border transition-colors flex-shrink-0
                     {$connected
                       ? 'bg-red-900/20 border-red-700/50 text-red-400 hover:bg-red-800/30 hover:border-red-600/70 cursor-pointer'
                       : 'bg-[#161920] border-[#2e3340] text-slate-700 cursor-not-allowed'}"
              on:click={() => requestAction('shutdown')}
            >
              Shut down
            </button>
          </div>

          <!-- Restart -->
          <div class="bg-[#1e2129] rounded-xl border border-[#2e3340] p-5 flex items-center gap-4">
            <div class="flex-1">
              <p class="text-sm font-semibold text-slate-200">Restart</p>
              <p class="text-xs text-slate-600 mt-0.5">
                Reboots the Raspberry Pi. The dashboard will reconnect automatically after ~30 seconds.
              </p>
            </div>
            <button
              disabled={!$connected}
              class="px-4 py-2 rounded-lg text-sm font-semibold border transition-colors flex-shrink-0
                     {$connected
                       ? 'bg-amber-900/20 border-amber-700/50 text-amber-400 hover:bg-amber-800/30 hover:border-amber-600/70 cursor-pointer'
                       : 'bg-[#161920] border-[#2e3340] text-slate-700 cursor-not-allowed'}"
              on:click={() => requestAction('reboot')}
            >
              Restart
            </button>
          </div>

          {#if !$connected}
            <p class="text-[11px] text-slate-700 text-center">
              Connect to the daemon before using power controls.
            </p>
          {/if}
        </div>

        <!-- Camera — runtime-only tuning, not persisted across restarts -->
        <div class="space-y-3 pt-6 mt-6 border-t border-[#2e3340]">
          <p class="text-xs text-slate-600 uppercase tracking-widest">Camera</p>
          <div class="bg-[#1e2129] rounded-xl border border-[#2e3340] p-5 space-y-4">
            <div>
              <p class="text-sm font-semibold text-slate-200">Resolution &amp; Frame Rate</p>
              <p class="text-xs text-slate-600 mt-0.5">
                Runtime only — resets to the default on restart. Useful for testing whether a
                lower resolution at a higher frame rate looks smoother than the default.
              </p>
            </div>
            <div class="flex flex-wrap gap-6">
              <div class="space-y-1.5">
                <p class="text-[10px] text-slate-600 uppercase tracking-widest">Resolution</p>
                <div class="flex gap-2">
                  {#each CAMERA_RESOLUTIONS as [w, h, label, dims]}
                    <button
                      disabled={!$connected}
                      class="flex flex-col items-center px-3 py-1.5 rounded text-xs font-semibold border transition-all leading-tight
                             {cameraConfig.width === w && cameraConfig.height === h
                               ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}
                             {!$connected ? 'opacity-50 cursor-not-allowed' : ''}"
                      on:click={() => setCameraResolution(w, h)}
                    >
                      <span>{label}</span>
                      <span class="text-[9px] font-normal opacity-70">{dims}</span>
                    </button>
                  {/each}
                </div>
              </div>
              <div class="space-y-1.5">
                <p class="text-[10px] text-slate-600 uppercase tracking-widest">Frame Rate</p>
                <div class="flex gap-2">
                  {#each CAMERA_FPS_OPTIONS as fps}
                    <button
                      disabled={!$connected}
                      class="px-3 py-1.5 rounded text-xs font-semibold border transition-all
                             {cameraConfig.fps === fps
                               ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                               : 'bg-[#161920] border-[#2e3340] text-slate-500 hover:border-slate-500 hover:text-slate-300'}
                             {!$connected ? 'opacity-50 cursor-not-allowed' : ''}"
                      on:click={() => setCameraFps(fps)}
                    >{fps} fps</button>
                  {/each}
                </div>
              </div>
            </div>
            <div class="pt-3 border-t border-[#2e3340] flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
              <span>Requested: <span class="text-slate-300 font-mono">{cameraConfig.width}×{cameraConfig.height} @ {cameraConfig.fps} fps</span></span>
              <span>Negotiated: <span class="text-slate-300 font-mono">{cameraConfig.actual_width ?? '—'}×{cameraConfig.actual_height ?? '—'}</span></span>
              <span>Measured: <span class="text-slate-300 font-mono">{cameraActualFps ?? '—'} fps</span></span>
            </div>
          </div>
        </div>

        <!-- Firmware — kept at the bottom, out of the way of everyday controls -->
        <div class="space-y-3 pt-6 mt-6 border-t border-[#2e3340]">
          <p class="text-xs text-slate-600 uppercase tracking-widest">RP2040 — Admin Only</p>

          {#if firmwareConfirming}
            <!-- Confirmation step -->
            <div class="bg-[#1e2129] rounded-xl border border-amber-700/40 p-6 space-y-4">
              <div class="flex items-center gap-3">
                <svg class="w-6 h-6 text-amber-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <p class="text-sm font-semibold text-slate-200">Flash the RP2040 now?</p>
              </div>
              <p class="text-xs text-slate-500">
                The robot will stop responding for a few seconds while the RP2040 reboots into its
                bootloader, gets reflashed, and restarts. Motors will not respond during this window.
              </p>
              <div class="flex gap-3 pt-1">
                <button
                  class="flex-1 py-2.5 rounded-lg text-sm font-bold bg-amber-700/30 border border-amber-600/60
                         text-amber-300 hover:bg-amber-700/50 transition-colors"
                  on:click={confirmFlash}
                >
                  Yes, flash firmware
                </button>
                <button
                  class="px-5 py-2.5 rounded-lg text-sm text-slate-400 border border-[#2e3340]
                         hover:text-slate-200 hover:border-slate-500 transition-colors"
                  on:click={cancelFlash}
                >
                  Cancel
                </button>
              </div>
            </div>

          {:else}
            <div class="bg-[#1e2129] rounded-xl border border-[#2e3340] p-5 flex items-center gap-4">
              <div class="flex-1">
                <p class="text-sm font-semibold text-slate-200">Flash Firmware</p>
                <p class="text-xs text-slate-600 mt-0.5">
                  Reflashes the RP2040 from the firmware built on this Pi — no need to unplug it or
                  press BOOTSEL. See the Debug Console for flash progress.
                </p>
              </div>
              <button
                disabled={!$connected || $flashStatus.state === 'running'}
                class="px-4 py-2 rounded-lg text-sm font-semibold border transition-colors flex-shrink-0
                       {$connected && $flashStatus.state !== 'running'
                         ? 'bg-blue-900/20 border-blue-700/50 text-blue-400 hover:bg-blue-800/30 hover:border-blue-600/70 cursor-pointer'
                         : 'bg-[#161920] border-[#2e3340] text-slate-700 cursor-not-allowed'}"
                on:click={requestFlash}
              >
                {$flashStatus.state === 'running' ? 'Flashing…' : 'Flash'}
              </button>
            </div>

            {#if $flashStatus.state === 'running'}
              <div class="flex items-center gap-2 px-1 text-xs text-blue-400">
                <svg class="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2a10 10 0 1 0 10 10" stroke-linecap="round"/>
                </svg>
                {$flashStatus.message}
              </div>
            {:else if $flashStatus.state === 'success'}
              <div class="flex items-center gap-2 px-1 text-xs text-emerald-400">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {$flashStatus.message}
              </div>
            {:else if $flashStatus.state === 'error'}
              <div class="flex items-center gap-2 px-1 text-xs text-red-400">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M15 9l-6 6M9 9l6 6" stroke-linecap="round"/>
                </svg>
                {$flashStatus.message}
              </div>
            {/if}

            {#if !$connected}
              <p class="text-[11px] text-slate-700 text-center">
                Connect to the daemon before flashing firmware.
              </p>
            {/if}
          {/if}
        </div>
      {/if}

    </div>
  </div>
</div>
