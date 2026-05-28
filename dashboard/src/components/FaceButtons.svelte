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

  // Idle: dim tinted background. Active: bright + glow + slight scale-down.
  const C = {
    a: { idle: 'rgba(42,160,80,0.25)',  active: 'rgba(42,220,90,0.90)',  glow: 'rgba(42,200,80,0.6)',  label: '#a7f3c0' },
    b: { idle: 'rgba(200,50,50,0.25)',  active: 'rgba(250,70,70,0.90)',  glow: 'rgba(230,60,60,0.6)',  label: '#fca5a5' },
    x: { idle: 'rgba(50,100,220,0.25)', active: 'rgba(80,140,255,0.90)', glow: 'rgba(70,130,255,0.6)', label: '#93c5fd' },
    y: { idle: 'rgba(200,160,20,0.25)', active: 'rgba(250,200,30,0.90)', glow: 'rgba(230,185,25,0.6)', label: '#fde68a' },
  };

  const BORDER = 'rgba(255,255,255,0.25)';

  $: aStyle = state.a
    ? `background:${C.a.active}; border-color:${C.a.glow}; color:${C.a.label}; box-shadow:0 0 14px ${C.a.glow}; transform:scale(0.91);`
    : `background:${C.a.idle};   border-color:${BORDER};    color:${C.a.label};`;
  $: bStyle = state.b
    ? `background:${C.b.active}; border-color:${C.b.glow}; color:${C.b.label}; box-shadow:0 0 14px ${C.b.glow}; transform:scale(0.91);`
    : `background:${C.b.idle};   border-color:${BORDER};    color:${C.b.label};`;
  $: xStyle = state.x
    ? `background:${C.x.active}; border-color:${C.x.glow}; color:${C.x.label}; box-shadow:0 0 14px ${C.x.glow}; transform:scale(0.91);`
    : `background:${C.x.idle};   border-color:${BORDER};    color:${C.x.label};`;
  $: yStyle = state.y
    ? `background:${C.y.active}; border-color:${C.y.glow}; color:${C.y.label}; box-shadow:0 0 14px ${C.y.glow}; transform:scale(0.91);`
    : `background:${C.y.idle};   border-color:${BORDER};    color:${C.y.label};`;

  const btnClass = `
    w-14 h-14 rounded-full flex items-center justify-center
    text-base font-bold select-none touch-none
    border-2 transition-all duration-75
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
  <div class={btnClass} style={yStyle}
    on:pointerdown|preventDefault={() => press('y')}
    on:pointerup={() => release('y')}
    on:pointercancel={() => release('y')}
    on:pointerleave={() => release('y')}
  >Y</div>
  <div></div>

  <!-- Row 2 -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={xStyle}
    on:pointerdown|preventDefault={() => press('x')}
    on:pointerup={() => release('x')}
    on:pointercancel={() => release('x')}
    on:pointerleave={() => release('x')}
  >X</div>
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={bStyle}
    on:pointerdown|preventDefault={() => press('b')}
    on:pointerup={() => release('b')}
    on:pointercancel={() => release('b')}
    on:pointerleave={() => release('b')}
  >B</div>

  <!-- Row 3 -->
  <div></div>
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class={btnClass} style={aStyle}
    on:pointerdown|preventDefault={() => press('a')}
    on:pointerup={() => release('a')}
    on:pointercancel={() => release('a')}
    on:pointerleave={() => release('a')}
  >A</div>
  <div></div>
</div>
