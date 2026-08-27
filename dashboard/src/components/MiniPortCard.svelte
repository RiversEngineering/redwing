<script>
  /**
   * MiniPortCard – skinny chip for PCA9685 channels in the I²C bus row.
   * Same height as PortCard (fills its stretched flex-row slot via h-full),
   * just narrower — there can be up to 16 of these next to the I²C/IMU cards.
   */
  import { accentClass, liveValue } from '../lib/ports.js';

  export let label;          // badge text, e.g. "P3"
  export let data = null;    // channel data, or null if unconfigured
  export let badgeClass = 'bg-slate-700/60 text-slate-400';
</script>

<div
  class="relative flex flex-col h-full w-12 flex-shrink-0 rounded-lg border transition-all duration-200 overflow-hidden
         {data
           ? `${accentClass(data.type)} bg-[#1e2129]`
           : 'text-slate-700 border-slate-800/50 bg-[#191c23]'}"
>
  <!-- Badge -->
  <div class="flex justify-center px-1 pt-2 pb-1">
    <span class="text-[9px] font-bold font-mono px-1 rounded leading-tight {badgeClass}">{label}</span>
  </div>

  <!-- Value, centered in whatever space remains -->
  <div class="flex flex-1 items-center justify-center px-1 pb-2">
    {#if data}
      <span class="text-[10px] font-mono font-semibold leading-tight text-center">
        {liveValue(data) ?? '·'}
      </span>
    {:else}
      <span class="text-[9px] text-slate-700 italic leading-tight">empty</span>
    {/if}
  </div>
</div>
