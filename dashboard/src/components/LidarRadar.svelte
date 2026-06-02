<script>
  import { robotState } from '../lib/stores.js';

  // Maximum range to render (cm). Points beyond this are clamped to the edge.
  const MAX_CM   = 400;
  // SVG coordinate radius (half the square viewBox side)
  const R        = 160;
  // Range rings to draw (cm)
  const RINGS    = [100, 200, 300, 400];

  $: scan    = $robotState?.lidar ?? [];
  $: hasData = scan.length > 0;

  /** Convert polar (angle °, distance cm) to SVG (x, y). 0° = top = forward. */
  function toXY(angle_deg, dist_cm) {
    const r   = Math.min(dist_cm, MAX_CM) / MAX_CM * R;
    const rad = (angle_deg - 90) * Math.PI / 180;
    return [R + r * Math.cos(rad), R + r * Math.sin(rad)];
  }
</script>

<div class="w-full h-full flex items-center justify-center"
     style="background:#040d04;">
  <svg
    viewBox="0 0 {R*2} {R*2}"
    class="w-full h-full"
    preserveAspectRatio="xMidYMid meet"
  >
    <!-- Radar background -->
    <circle cx={R} cy={R} r={R} fill="#040d04" />

    <!-- Range rings -->
    {#each RINGS as ring_cm}
      {@const rr = ring_cm / MAX_CM * R}
      <circle cx={R} cy={R} r={rr}
              fill="none" stroke="#0d3a0d" stroke-width="0.5" />
      <text x={R + rr + 2} y={R + 4}
            fill="#175917" font-size="7" font-family="monospace"
      >{ring_cm}cm</text>
    {/each}

    <!-- Cardinal axes -->
    <line x1={R} y1="0"   x2={R}   y2={R*2} stroke="#0d3a0d" stroke-width="0.5" />
    <line x1="0" y1={R}   x2={R*2} y2={R}   stroke="#0d3a0d" stroke-width="0.5" />

    <!-- Forward indicator -->
    <text x={R} y="11" text-anchor="middle"
          fill="#22c55e" font-size="9" font-family="sans-serif" opacity="0.6">▲</text>

    <!-- LIDAR points -->
    {#if hasData}
      {#each scan as [angle, dist]}
        {@const [px, py] = toXY(angle, dist)}
        <circle cx={px} cy={py} r="1.8" fill="#4ade80" opacity="0.8" />
      {/each}
    {:else}
      <text x={R} y={R - 8}  text-anchor="middle"
            fill="#175917" font-size="11" font-family="sans-serif">No LIDAR data</text>
      <text x={R} y={R + 8}  text-anchor="middle"
            fill="#0d3a0d" font-size="8"  font-family="sans-serif">Set REDWING_LIDAR in compose</text>
    {/if}

    <!-- Robot dot (center) -->
    <circle cx={R} cy={R} r="4"   fill="#4ade80" />
    <circle cx={R} cy={R} r="1.5" fill="#040d04" />
  </svg>
</div>
