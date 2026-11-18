<script>
  import { robotState } from '../lib/stores.js';
  import { scanToRobot } from '../lib/lidar.js';

  const R = 160;   // SVG coordinate radius

  $: cfg     = $robotState?.lidar_config ?? {};
  $: maxCm   = cfg.max_cm   ?? 400;

  $: scan    = $robotState?.lidar ?? [];
  $: hasData = scan.length > 0;

  // Range rings: four evenly-spaced rings scaled to maxCm
  $: rings = [0.25, 0.5, 0.75, 1.0].map(f => Math.round(f * maxCm));

  // Robot-frame points (+x forward, +y left), mounting offsets applied
  $: points = scanToRobot(scan, cfg).map(([x, y]) => toSvg(x, y));

  /** Robot-frame (x forward, y left) → SVG, forward = top, left = left.
   *  Points beyond maxCm are pulled in to the outer ring. */
  function toSvg(x, y) {
    const d = Math.sqrt(x * x + y * y);
    const k = (d > maxCm ? maxCm / d : 1) * R / maxCm;
    return [R - y * k, R - x * k];
  }
</script>

<div class="w-full h-full flex items-center justify-center"
     style="background:#040d04;">
  <svg
    viewBox="0 0 {R*2} {R*2}"
    class="w-full h-full"
    preserveAspectRatio="xMidYMid meet"
  >
    <circle cx={R} cy={R} r={R} fill="#040d04" />

    <!-- Range rings (scaled to maxCm) -->
    {#each rings as ring_cm, i}
      {@const rr = (ring_cm / maxCm) * R}
      <circle cx={R} cy={R} r={rr}
              fill="none" stroke="#0d3a0d" stroke-width="0.5" />
      <text x={R + rr + 2} y={R + 4}
            fill="#175917" font-size="7" font-family="monospace"
      >{ring_cm}cm</text>
    {/each}

    <!-- Cardinal axes -->
    <line x1={R} y1="0"   x2={R}   y2={R*2} stroke="#0d3a0d" stroke-width="0.5" />
    <line x1="0" y1={R}   x2={R*2} y2={R}   stroke="#0d3a0d" stroke-width="0.5" />

    <!-- Forward label (always top = robot forward) -->
    <text x={R} y="11" text-anchor="middle"
          fill="#22c55e" font-size="9" font-family="sans-serif" opacity="0.6">▲</text>

    <!-- LIDAR points (mounting offsets applied in scanToRobot) -->
    {#if hasData}
      {#each points as [px, py]}
        <circle cx={px} cy={py} r="1.8" fill="#4ade80" opacity="0.8" />
      {/each}
    {:else}
      <text x={R} y={R - 8}  text-anchor="middle"
            fill="#175917" font-size="11" font-family="sans-serif">No LIDAR data</text>
      <text x={R} y={R + 8}  text-anchor="middle"
            fill="#0d3a0d" font-size="8"  font-family="sans-serif">Set REDWING_LIDAR in compose</text>
    {/if}

    <!-- Robot indicator -->
    <circle cx={R} cy={R} r="4"   fill="#4ade80" />
    <circle cx={R} cy={R} r="1.5" fill="#040d04" />
  </svg>
</div>
