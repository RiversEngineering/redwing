<script>
  import { onMount } from 'svelte';
  import { connected, cameraFrame } from '../lib/stores.js';

  let canvas;
  let wrapper;
  let pickerMode = false;
  let sampled    = null;   // { hex, r, g, b, h_ocv, s_ocv, v_ocv, isRed, py_lo, py_hi, py_lo2?, py_hi2? }
  let overlayX   = 0;
  let overlayY   = 0;
  let copied     = false;

  // ── Canvas sizing ──────────────────────────────────────────────────────────

  function syncCanvasSize() {
    if (!canvas || !wrapper) return;
    canvas.width  = wrapper.offsetWidth;
    canvas.height = wrapper.offsetHeight;
    drawFrame($cameraFrame);
  }

  onMount(() => {
    syncCanvasSize();
    const ro = new ResizeObserver(syncCanvasSize);
    ro.observe(wrapper);
    return () => ro.disconnect();
  });

  // ── Frame rendering ────────────────────────────────────────────────────────

  let _imgRect = null;   // { dx, dy, dw, dh } of the letterboxed image on canvas

  function drawFrame(b64) {
    if (!canvas || !b64) return;
    const img = new Image();
    img.src = 'data:image/jpeg;base64,' + b64;
    img.onload = () => {
      const cw = canvas.width, ch = canvas.height;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, cw, ch);
      const scale = Math.min(cw / img.width, ch / img.height);
      const dw = img.width  * scale;
      const dh = img.height * scale;
      const dx = (cw - dw) / 2;
      const dy = (ch - dh) / 2;
      ctx.drawImage(img, dx, dy, dw, dh);
      _imgRect = { dx, dy, dw, dh };
    };
  }

  $: if (canvas) drawFrame($cameraFrame);

  // ── Colour math ────────────────────────────────────────────────────────────

  function rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    let h = 0;
    const s = max === 0 ? 0 : d / max;
    if (d !== 0) {
      if      (max === r) h = ((g - b) / d % 6) * 60;
      else if (max === g) h = ((b - r) / d + 2) * 60;
      else                h = ((r - g) / d + 4) * 60;
      if (h < 0) h += 360;
    }
    return [h, s, max];   // h: 0-360, s: 0-1, v: 0-1
  }

  function handleClick(e) {
    if (!pickerMode || !canvas) return;
    const ctx  = canvas.getContext('2d');
    const data = ctx.getImageData(e.offsetX, e.offsetY, 1, 1).data;
    const [r, g, b] = [data[0], data[1], data[2]];

    const hex   = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
    const [h, s, v] = rgbToHsv(r, g, b);

    // OpenCV HSV scale: H 0-180, S 0-255, V 0-255
    const h_ocv = Math.round(h / 2);
    const s_ocv = Math.round(s * 255);
    const v_ocv = Math.round(v * 255);

    const hMargin = 15;
    const sLo     = Math.max(0,   s_ocv - 60);
    const vLo     = Math.max(0,   v_ocv - 60);
    const isRed   = h_ocv < 15 || h_ocv > 165;

    let py_lo, py_hi, py_lo2 = null, py_hi2 = null;
    if (isRed) {
      py_lo  = [0,   sLo, vLo];
      py_hi  = [15,  255, 255];
      py_lo2 = [165, sLo, vLo];
      py_hi2 = [180, 255, 255];
    } else {
      py_lo = [Math.max(0,   h_ocv - hMargin), sLo, vLo];
      py_hi = [Math.min(180, h_ocv + hMargin), 255, 255];
    }

    sampled  = { hex, r, g, b, h_ocv, s_ocv, v_ocv, isRed, py_lo, py_hi, py_lo2, py_hi2 };
    overlayX = e.offsetX;
    overlayY = e.offsetY;
    copied   = false;
  }

  // ── Python snippet ─────────────────────────────────────────────────────────

  function fmt(arr) { return `[${arr.join(', ')}]`; }

  function pySnippet(s) {
    if (!s) return '';
    if (s.isRed) {
      return (
        `hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)\n` +
        `mask = cv2.inRange(hsv, np.array(${fmt(s.py_lo)}), np.array(${fmt(s.py_hi)})) | \\\n` +
        `       cv2.inRange(hsv, np.array(${fmt(s.py_lo2)}), np.array(${fmt(s.py_hi2)}))`
      );
    }
    return (
      `hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)\n` +
      `mask = cv2.inRange(hsv, np.array(${fmt(s.py_lo)}), np.array(${fmt(s.py_hi)}))`
    );
  }

  async function copySnippet() {
    if (!sampled) return;
    const full = `import cv2\nimport numpy as np\n\n# Sampled colour: ${sampled.hex}\n${pySnippet(sampled)}`;
    await navigator.clipboard.writeText(full);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }

  // ── Overlay positioning ────────────────────────────────────────────────────
  // Keep the 288 px-wide overlay within the wrapper bounds.

  const OVERLAY_W = 288;
  const OVERLAY_H = 180;   // approximate; enough to avoid bottom-edge clipping

  $: overlayLeft = (wrapper && overlayX + OVERLAY_W + 12 < wrapper.offsetWidth)
      ? overlayX + 12
      : overlayX - OVERLAY_W - 4;

  $: overlayTop  = (wrapper && overlayY + OVERLAY_H < wrapper.offsetHeight)
      ? overlayY + 8
      : overlayY - OVERLAY_H;
</script>

<div class="flex flex-col h-full bg-[#1e2129] rounded-lg border border-[#2e3340] overflow-hidden">

  <!-- Header ---------------------------------------------------------------->
  <div class="flex items-center gap-2 px-3 py-2 border-b border-[#2e3340] flex-shrink-0">
    <!-- camera icon -->
    <svg class="w-4 h-4 text-slate-400 flex-shrink-0" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="3" width="14" height="10" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.2"/>
      <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Camera</span>

    <div class="ml-auto flex items-center gap-2">
      {#if $connected && $cameraFrame}
        <span class="text-[10px] text-emerald-400 font-mono">LIVE</span>
      {/if}

      <!-- Colour picker toggle -->
      <button
        on:click={() => { pickerMode = !pickerMode; if (!pickerMode) sampled = null; }}
        class="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors
               {pickerMode
                 ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                 : 'text-slate-500 border border-transparent hover:text-slate-300 hover:border-slate-600'}"
        title="Sample a colour from the frame for HSV colour tracking"
      >
        <!-- pipette / eyedropper icon -->
        <svg class="w-3 h-3" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M11 2l3 3-7 7-1.5 0.5L6 11l0.5-1.5L11 2z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
          <path d="M3 13l2-2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          <path d="M9.5 3.5l3 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
        PICK
      </button>
    </div>
  </div>

  <!-- Video area ------------------------------------------------------------->
  <div class="relative flex-1 bg-black overflow-hidden min-h-0" bind:this={wrapper}>

    {#if $connected && $cameraFrame}

      <canvas
        bind:this={canvas}
        class="w-full h-full block {pickerMode ? 'cursor-crosshair' : ''}"
        on:click={handleClick}
      />

      <!-- Pick-mode hint bar -->
      {#if pickerMode && !sampled}
        <div class="absolute inset-x-0 bottom-3 flex justify-center pointer-events-none">
          <div class="bg-black/70 text-amber-300 text-[10px] font-mono px-3 py-1 rounded-full">
            Click anywhere on the image to sample a colour
          </div>
        </div>
      {/if}

      <!-- Colour overlay -->
      {#if pickerMode && sampled}
        <div
          class="absolute z-10 w-72 bg-[#12151d] border border-[#3a4258] rounded-xl shadow-2xl p-3 select-none"
          style="left: {overlayLeft}px; top: {overlayTop}px;"
        >
          <!-- Swatch + hex -->
          <div class="flex items-center gap-2 mb-2">
            <div
              class="w-9 h-9 rounded-md border border-white/10 flex-shrink-0"
              style="background: {sampled.hex}"
            />
            <div>
              <div class="text-white font-mono font-bold text-sm">{sampled.hex.toUpperCase()}</div>
              <div class="text-slate-400 text-[10px] font-mono">
                RGB({sampled.r}, {sampled.g}, {sampled.b})
              </div>
            </div>
            <!-- close -->
            <button
              on:click={() => (sampled = null)}
              class="ml-auto text-slate-500 hover:text-slate-300 leading-none text-base px-1"
              title="Dismiss"
            >✕</button>
          </div>

          <!-- HSV row -->
          <div class="text-[10px] font-mono text-slate-400 mb-2 bg-[#1a1d28] rounded px-2 py-1">
            OpenCV HSV&nbsp;&nbsp;H={sampled.h_ocv}&nbsp;&nbsp;S={sampled.s_ocv}&nbsp;&nbsp;V={sampled.v_ocv}
            {#if sampled.isRed}<span class="text-amber-400 ml-1">(red wraps — two ranges)</span>{/if}
          </div>

          <!-- Python snippet -->
          <pre class="text-[10px] font-mono bg-[#0b0d14] text-emerald-300 rounded-lg p-2 overflow-x-auto leading-relaxed mb-2 whitespace-pre">{pySnippet(sampled)}</pre>

          <!-- Copy button -->
          <button
            on:click={copySnippet}
            class="w-full text-[11px] font-mono py-1 rounded-md transition-colors
                   {copied
                     ? 'bg-emerald-600/30 text-emerald-400 border border-emerald-600/40'
                     : 'bg-[#1e2230] text-slate-300 border border-[#3a4258] hover:bg-[#262b3d]'}"
          >
            {#if copied}
              <span>✓ Copied to clipboard</span>
            {:else}
              <span>Copy snippet</span>
            {/if}
          </button>
        </div>
      {/if}

    {:else}
      <!-- No signal placeholder -->
      <div class="flex flex-col items-center justify-center h-full gap-3 text-slate-600">
        <svg class="w-12 h-12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="2" y="4" width="20" height="15" rx="2" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 19v2M16 19v2M5 21h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="3" y1="3" x2="21" y2="21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span class="text-sm font-medium">
          {$connected ? 'No camera signal' : 'Waiting for connection…'}
        </span>
      </div>
    {/if}

  </div>
</div>
