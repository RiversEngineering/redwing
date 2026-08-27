<script>
  /**
   * MiniPortCard – small square chip for dense rows (I²C sensor, IMU,
   * PCA9685 channels) where a full-size PortCard would take too much space.
   */
  import { accentClass, liveValue } from '../lib/ports.js';

  export let label;          // badge text, e.g. "I²C", "IMU", "P3"
  export let data = null;    // port/channel data, or null if unconfigured
  export let badgeClass = 'bg-slate-700/60 text-slate-400';
</script>

<div
  class="flex flex-col items-center justify-center gap-0.5 w-11 h-11 flex-shrink-0 rounded-md border
         {data ? 'border-[#2e3340] bg-[#1e2129]' : 'border-slate-800/50 bg-[#191c23]'}"
>
  <span class="text-[9px] font-bold font-mono px-1 rounded leading-tight {badgeClass}">{label}</span>
  {#if data}
    <span class="text-[9px] font-mono leading-none truncate max-w-full px-0.5 {accentClass(data.type).split(' ')[0]}">
      {liveValue(data) ?? '·'}
    </span>
  {:else}
    <span class="text-[8px] text-slate-700 italic leading-none">empty</span>
  {/if}
</div>
