<script>
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  let state = { up: false, down: false, left: false, right: false };

  function press(dir) {
    state = { ...state, [dir]: true };
    dispatch('change', { ...state });
  }

  function release(dir) {
    state = { ...state, [dir]: false };
    dispatch('change', { ...state });
  }

  const btnClass = `
    flex items-center justify-center select-none touch-none
    rounded-md text-slate-300 text-xl font-bold
    transition-colors duration-75
  `;
  const activeStyle = 'background: rgba(100,140,255,0.5); border-color: rgba(100,140,255,0.8);';
  const inactiveStyle = 'background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.18);';

  $: upStyle    = state.up    ? activeStyle : inactiveStyle;
  $: downStyle  = state.down  ? activeStyle : inactiveStyle;
  $: leftStyle  = state.left  ? activeStyle : inactiveStyle;
  $: rightStyle = state.right ? activeStyle : inactiveStyle;
</script>

<!-- D-pad: + shape using a 3×3 CSS grid -->
<div class="grid" style="grid-template-columns: repeat(3, 52px); grid-template-rows: repeat(3, 52px); gap: 4px;">
  <!-- Row 1: empty / up / empty -->
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class={btnClass}
    style="border: 1.5px solid; {upStyle}"
    on:pointerdown|preventDefault={() => press('up')}
    on:pointerup={() => release('up')}
    on:pointercancel={() => release('up')}
    on:pointerleave={() => release('up')}
  >▲</div>
  <div></div>

  <!-- Row 2: left / center / right -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class={btnClass}
    style="border: 1.5px solid; {leftStyle}"
    on:pointerdown|preventDefault={() => press('left')}
    on:pointerup={() => release('left')}
    on:pointercancel={() => release('left')}
    on:pointerleave={() => release('left')}
  >◀</div>
  <!-- Center pip -->
  <div class="rounded-md" style="background: rgba(255,255,255,0.04); border: 1.5px solid rgba(255,255,255,0.08);"></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class={btnClass}
    style="border: 1.5px solid; {rightStyle}"
    on:pointerdown|preventDefault={() => press('right')}
    on:pointerup={() => release('right')}
    on:pointercancel={() => release('right')}
    on:pointerleave={() => release('right')}
  >▶</div>

  <!-- Row 3: empty / down / empty -->
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class={btnClass}
    style="border: 1.5px solid; {downStyle}"
    on:pointerdown|preventDefault={() => press('down')}
    on:pointerup={() => release('down')}
    on:pointercancel={() => release('down')}
    on:pointerleave={() => release('down')}
  >▼</div>
  <div></div>
</div>
