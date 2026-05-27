<script>
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  let state = { a: false, b: false, x: false, y: false };

  function press(btn) {
    state = { ...state, [btn]: true };
    dispatch('change', { ...state });
  }

  function release(btn) {
    state = { ...state, [btn]: false };
    dispatch('change', { ...state });
  }

  // Xbox colour palette
  const COLORS = {
    a: { idle: 'rgba(42,160,80,0.5)',  active: 'rgba(42,200,80,0.85)',  border: 'rgba(42,180,80,0.8)',  label: '#a7f3c0' },
    b: { idle: 'rgba(200,50,50,0.5)',  active: 'rgba(240,60,60,0.85)',  border: 'rgba(220,60,60,0.8)',  label: '#fca5a5' },
    x: { idle: 'rgba(50,100,220,0.5)', active: 'rgba(70,130,255,0.85)', border: 'rgba(60,120,240,0.8)', label: '#93c5fd' },
    y: { idle: 'rgba(200,160,20,0.5)', active: 'rgba(240,190,30,0.85)', border: 'rgba(220,175,25,0.8)', label: '#fde68a' },
  };

  function btnStyle(btn) {
    const c = COLORS[btn];
    return state[btn]
      ? `background:${c.active}; border-color:${c.border}; color:${c.label};`
      : `background:${c.idle};  border-color:${c.border}; color:${c.label};`;
  }

  const btnClass = `
    w-14 h-14 rounded-full flex items-center justify-center
    text-base font-bold select-none touch-none
    border-2 transition-all duration-75
    shadow-lg
  `;
</script>

<!--
  Diamond layout (Xbox / GameSir):
       [Y]
  [X]       [B]
       [A]
-->
<div class="grid" style="grid-template-columns: repeat(3, 56px); grid-template-rows: repeat(3, 56px); gap: 4px;">
  <!-- Row 1 -->
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={btnStyle('y')}
    on:pointerdown|preventDefault={() => press('y')}
    on:pointerup={() => release('y')}
    on:pointercancel={() => release('y')}
    on:pointerleave={() => release('y')}
  >Y</div>
  <div></div>

  <!-- Row 2 -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={btnStyle('x')}
    on:pointerdown|preventDefault={() => press('x')}
    on:pointerup={() => release('x')}
    on:pointercancel={() => release('x')}
    on:pointerleave={() => release('x')}
  >X</div>
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={btnStyle('b')}
    on:pointerdown|preventDefault={() => press('b')}
    on:pointerup={() => release('b')}
    on:pointercancel={() => release('b')}
    on:pointerleave={() => release('b')}
  >B</div>

  <!-- Row 3 -->
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={btnStyle('a')}
    on:pointerdown|preventDefault={() => press('a')}
    on:pointerup={() => release('a')}
    on:pointercancel={() => release('a')}
    on:pointerleave={() => release('a')}
  >A</div>
  <div></div>
</div>
