<script>
  import { connected } from '../lib/stores.js';

  // Build camera URL from current host
  const cameraUrl = `http://${location.host}/camera`;

  let imgEl;
  let imgError = false;

  function handleError() {
    imgError = true;
  }

  function handleLoad() {
    imgError = false;
  }

  // When we reconnect, refresh the MJPEG src to re-establish the stream
  $: if ($connected) {
    imgError = false;
    if (imgEl) {
      // Force reload by toggling src
      const src = cameraUrl;
      imgEl.src = '';
      requestAnimationFrame(() => { imgEl.src = src; });
    }
  }
</script>

<div class="flex flex-col h-full bg-[#1e2129] rounded-lg border border-[#2e3340] overflow-hidden">
  <!-- Panel header -->
  <div class="flex items-center gap-2 px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="3" width="14" height="10" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.2"/>
      <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Camera</span>
    {#if $connected && !imgError}
      <span class="ml-auto text-[10px] text-emerald-400 font-mono">LIVE</span>
    {/if}
  </div>

  <!-- Video area -->
  <div class="relative flex-1 flex items-center justify-center bg-black overflow-hidden min-h-0">
    {#if $connected}
      <!-- MJPEG stream -->
      <img
        bind:this={imgEl}
        src={cameraUrl}
        alt="Robot camera feed"
        on:error={handleError}
        on:load={handleLoad}
        class="w-full h-full object-contain"
        class:hidden={imgError}
      />
      {#if imgError}
        <div class="flex flex-col items-center gap-2 text-slate-500">
          <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="2" y="4" width="20" height="15" rx="2" stroke="currentColor" stroke-width="1.5"/>
            <path d="M8 19v2M16 19v2M5 21h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M9 10l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="text-sm">No camera signal</span>
        </div>
      {/if}
    {:else}
      <!-- Disconnected placeholder -->
      <div class="flex flex-col items-center gap-3 text-slate-600">
        <svg class="w-12 h-12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="4" width="20" height="15" rx="2" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 19v2M16 19v2M5 21h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="3" y1="3" x2="21" y2="21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span class="text-sm font-medium">No camera</span>
        <span class="text-xs text-slate-700">Waiting for connection…</span>
      </div>
    {/if}
  </div>
</div>
