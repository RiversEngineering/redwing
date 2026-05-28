<script>
  import { createEventDispatcher } from 'svelte';

  export let label = 'LB';

  const dispatch = createEventDispatcher();

  let latched = false;
  let held    = false;
  let pressStart = 0;

  const TOGGLE_MS = 350;   // taps shorter than this toggle the latch

  $: active = latched || held;

  function onDown(e) {
    e.preventDefault();
    pressStart = Date.now();
    held = true;
    dispatch('change', { active: true, latched });
  }

  function onUp() {
    const duration = Date.now() - pressStart;
    held = false;
    if (duration < TOGGLE_MS) {
      latched = !latched;   // short tap → toggle latch
    }
    // long press: just release the hold; latch stays as-is
    dispatch('change', { active: latched, latched });
  }

  function onCancel() {
    held = false;
    dispatch('change', { active: latched, latched });
  }

  /** Called by parent to clear latch (e.g. when physical gamepad connects). */
  export function reset() {
    latched = false;
    held    = false;
    dispatch('change', { active: false, latched: false });
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="relative flex items-center justify-center select-none touch-none
         rounded-lg text-xs font-bold uppercase tracking-wider border-2
         transition-all duration-75"
  style="
    width: 54px; height: 38px;
    {active
      ? 'background:rgba(100,140,255,0.75); border-color:rgba(120,160,255,0.9); color:#ddeeff;'
      : 'background:rgba(255,255,255,0.08); border-color:rgba(255,255,255,0.18); color:#64748b;'}
  "
  on:pointerdown={onDown}
  on:pointerup={onUp}
  on:pointercancel={onCancel}
  on:pointerleave={onCancel}
>
  {label}
  {#if latched}
    <!-- small dot signals "latched on" vs a momentary hold -->
    <div class="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
         style="background:rgba(180,210,255,0.9);"></div>
  {/if}
</div>
