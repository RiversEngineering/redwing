<script>
  import { createEventDispatcher } from 'svelte';

  /** Outer radius of the touch zone in pixels */
  export let size = 72;

  const dispatch = createEventDispatcher();

  let active = false;
  let thumbX = 0;
  let thumbY = 0;
  let originX = 0;
  let originY = 0;

  const thumbR = Math.round(size * 0.35);   // thumb circle radius
  const maxTravel = size - thumbR - 4;      // max distance thumb moves from center

  function onPointerDown(e) {
    e.currentTarget.setPointerCapture(e.pointerId);
    const rect = e.currentTarget.getBoundingClientRect();
    originX = rect.left + rect.width  / 2;
    originY = rect.top  + rect.height / 2;
    active = true;
    move(e.clientX, e.clientY);
  }

  function onPointerMove(e) {
    if (!active) return;
    move(e.clientX, e.clientY);
  }

  function onPointerUp() {
    active = false;
    thumbX = 0;
    thumbY = 0;
    dispatch('change', { x: 0, y: 0 });
  }

  function move(cx, cy) {
    let dx = cx - originX;
    let dy = cy - originY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > maxTravel) {
      dx = (dx / dist) * maxTravel;
      dy = (dy / dist) * maxTravel;
    }
    thumbX = dx;
    thumbY = dy;
    dispatch('change', {
      x:  +(dx / maxTravel).toFixed(3),
      y: -(dy / maxTravel).toFixed(3),   // invert Y: up = positive
    });
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="joystick-zone relative rounded-full select-none touch-none"
  style="
    width:  {size * 2}px;
    height: {size * 2}px;
    background: rgba(255,255,255,0.06);
    border: 2px solid rgba(255,255,255,0.15);
    box-shadow: inset 0 0 {size * 0.3}px rgba(0,0,0,0.4);
  "
  on:pointerdown={onPointerDown}
  on:pointermove={onPointerMove}
  on:pointerup={onPointerUp}
  on:pointercancel={onPointerUp}
>
  <!-- Center cross-hair lines -->
  <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
    <div style="width:1px; height:{size * 1.2}px; background:rgba(255,255,255,0.08);"></div>
  </div>
  <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
    <div style="width:{size * 1.2}px; height:1px; background:rgba(255,255,255,0.08);"></div>
  </div>

  <!-- Thumb -->
  <div
    class="absolute rounded-full pointer-events-none"
    style="
      width:  {thumbR * 2}px;
      height: {thumbR * 2}px;
      top:  50%;
      left: 50%;
      transform: translate(calc(-50% + {thumbX}px), calc(-50% + {thumbY}px));
      background: {active
        ? 'radial-gradient(circle at 35% 35%, rgba(120,160,255,0.9), rgba(60,100,220,0.85))'
        : 'radial-gradient(circle at 35% 35%, rgba(200,210,230,0.5), rgba(120,140,180,0.4))'};
      border: 1.5px solid rgba(255,255,255,0.3);
      box-shadow: 0 2px 8px rgba(0,0,0,0.5);
      transition: background 0.1s;
    "
  ></div>
</div>
