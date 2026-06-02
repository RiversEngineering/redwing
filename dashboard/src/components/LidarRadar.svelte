<script>
  import { robotState } from '../lib/stores.js';

  const R = 160;   // SVG coordinate radius

  $: cfg     = $robotState?.lidar_config ?? {};
  $: offset  = cfg.offset   ?? 0;
  $: xOff    = cfg.x_offset ?? 0;
  $: yOff    = cfg.y_offset ?? 0;
  $: maxCm   = cfg.max_cm   ?? 400;

  $: scan    = $robotState?.lidar ?? [];
  $: hasData = scan.length > 0;

  // Range rings: four evenly-spaced rings scaled to maxCm
  $: rings = [0.25, 0.5, 0.75, 1.0].map(f => Math.round(f * maxCm));

  /** Convert polar (sensor angle °, distance cm) to SVG (x, y).
   *  Applies rotation offset and XY mounting offset. */
  function toXY(angle_deg, dist_cm) {
    // 1. Apply rotation offset
    const corrected = (angle_deg - offset + 360) % 360;
    const rad = corrected * Math.PI / 180;

    // 2. Sensor Cartesian (0° = forward = +Y, 90° = right = +X)
    let sx = dist_cm * Math.sin(rad);
    let sy = dist_cm * Math.cos(rad);

    // 3. Translate to robot-centre frame if XY offset is set
    if (xOff !== 0 || yOff !== 0) {
      const rx = sx + xOff;
      const ry = sy + yOff;
      const newDist  = Math.sqrt(rx * rx + ry * ry);
      const newAngle = (Math.atan2(rx, ry) * 180 / Math.PI + 360) % 360;
      sx = newDist * Math.sin(newAngle * Math.PI / 180);
      sy = newDist * Math.cos(newAngle * Math.PI / 180);
    }

    // 4. Clamp to maxCm and convert to SVG coords (SVG: +Y is down, -90° = top)
    const dist2 = Math.sqrt(sx * sx + sy * sy);
    const r     = Math.min(dist2, maxCm) / maxCm * R;
    const svgRad = Math.atan2(sx, sy) - Math.PI / 2; // rotate so forward = top
    return [R + r * Math.cos(svgRad), R + r * Math.sin(svgRad)];
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

    <!-- LIDAR points (offset already baked into toXY) -->
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

    <!-- Robot indicator -->
    <circle cx={R} cy={R} r="4"   fill="#4ade80" />
    <circle cx={R} cy={R} r="1.5" fill="#040d04" />
  </svg>
</div>
