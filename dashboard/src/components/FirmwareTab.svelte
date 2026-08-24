<script>
  import { send } from '../lib/ws.js';
  import { connected, flashStatus } from '../lib/stores.js';

  let confirming = false;

  function requestFlash() {
    confirming = true;
  }

  function cancel() {
    confirming = false;
  }

  function confirmFlash() {
    confirming = false;
    send({ cmd: 'flash_firmware' });
  }
</script>

<div class="flex flex-col h-full bg-[#161920] text-slate-200">

  <!-- Header -->
  <div class="flex items-center gap-2 px-4 py-2 border-b border-[#2e3340] bg-[#1a1d26] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <rect x="4" y="2" width="16" height="20" rx="2"/>
      <path d="M9 8h6M9 12h6M9 16h3"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Firmware</span>
  </div>

  <!-- Content -->
  <div class="flex-1 flex items-start justify-center p-8">
    <div class="max-w-md w-full space-y-8">

      {#if confirming}
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
              on:click={cancel}
            >
              Cancel
            </button>
          </div>
        </div>

      {:else}
        <!-- Normal state -->
        <div class="space-y-3">
          <p class="text-xs text-slate-600 uppercase tracking-widest">RP2040</p>

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
        </div>
      {/if}

    </div>
  </div>
</div>
