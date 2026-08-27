<script>
  /**
   * MiniPortCard – compact chip for PCA9685 channels in the I²C bus row.
   * Sits in a 2-row grid (see PortGrid), so each chip is only about half the
   * height of a full PortCard — label on top, reading stacked below it.
   */
  import { accentClass, liveValue } from '../lib/ports.js';

  export let label;          // badge text, e.g. "P3"
  export let data = null;    // channel data, or null if unconfigured
  export let badgeClass = 'bg-slate-700/60 text-slate-400';

  // The direction-role half of a PCA9685 sign-magnitude pair (see
  // pca_pair_channels in daemon/api.py) has no live value of its own — it's
  // a fixed high/low level, not a readout — so show where its pair lives
  // instead of a misleading "0% pwr".
  $: isPairDir = data?.type === 'motor_sm_pair' && data?.role === 'direction';
</script>

<div
  class="relative flex flex-col items-center justify-center gap-0.5 h-full w-full rounded-md border overflow-hidden
         {isPairDir
           ? 'text-slate-600 border-slate-800/50 bg-[#191c23] opacity-50'
           : data
             ? `${accentClass(data.type)} bg-[#1e2129]`
             : 'text-slate-700 border-slate-800/50 bg-[#191c23]'}"
  title={isPairDir ? `Paired with P${data.partner}` : undefined}
>
  <span class="text-[8px] font-bold font-mono px-1 rounded leading-none {badgeClass}">{label}</span>
  {#if isPairDir}
    <span class="text-[7px] font-mono leading-none truncate max-w-full">→P{data.partner}</span>
  {:else if data}
    <span class="text-[8px] font-mono font-semibold leading-none truncate max-w-full">
      {liveValue(data) ?? '·'}
    </span>
  {/if}
</div>
