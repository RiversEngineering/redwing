<script>
  /**
   * MapTab — world-centric persistent map built from robot.map_point() calls.
   *
   * Coordinate system:
   *   World x = right (cm), world y = forward (cm).
   *   SVG uses cy = -y to flip the Y axis so forward = up on screen.
   *
   * Data sources:
   *   mapPoints store  — accumulated obstacle points pushed by student code
   *   mapPose   store  — latest robot pose from robot.map_pose()
   *   $robotState.lidar — current LIDAR scan, overlaid when pose is known
   */
  import { send } from '../lib/ws.js';
  import { mapPoints, mapPose, clearMap, robotShapeRects } from '../lib/stores.js';
  import { robotState } from '../lib/stores.js';

  // ── Robot shape editor ────────────────────────────────────────────────────
  let showShapePanel = false;
  let newW = 30, newH = 40, newX = 0, newY = 0, newLabel = '';

  function addRect() {
    robotShapeRects.update(rects => [
      ...rects,
      { id: Date.now(), label: newLabel || `${newW}×${newH}`, width: newW, height: newH, x: newX, y: newY }
    ]);
    newW = 30; newH = 40; newX = 0; newY = 0; newLabel = '';
  }

  function deleteRect(id) {
    robotShapeRects.update(rects => rects.filter(r => r.id !== id));
  }

  // Pose to use for shape rendering: real pose or origin fallback
  $: shapePose = $mapPose ?? { x: 0, y: 0, heading: 0 };
  // SVG group transform: translate to pose, rotate by heading (CW in SVG = CW in world ✓)
  $: shapeTransform = `translate(${shapePose.x},${-shapePose.y}) rotate(${shapePose.heading})`;

  // ── View state ─────────────────────────────────────────────────────────────
  let viewCX    = 0;     // world-X at viewport centre (cm)
  let viewCY    = 0;     // world-Y at viewport centre (cm)
  let viewRange = 300;   // half-width of the viewport (cm)

  // ── Derived bounds ─────────────────────────────────────────────────────────
  $: viewBox = `${viewCX - viewRange} ${-(viewCY + viewRange)} ${viewRange * 2} ${viewRange * 2}`;

  // ── Grid ───────────────────────────────────────────────────────────────────
  function gridStep(range) {
    const raw = range / 3;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    if (raw / pow < 2) return pow;
    if (raw / pow < 5) return 2 * pow;
    return 5 * pow;
  }

  $: step = gridStep(viewRange);
  $: gridLines = (() => {
    const lines = [];
    const lo = Math.floor((viewCX - viewRange) / step) * step;
    const hi = Math.ceil ((viewCX + viewRange) / step) * step;
    for (let v = lo; v <= hi; v += step) {
      lines.push({ vertical: true,  v });
    }
    const loY = Math.floor((viewCY - viewRange) / step) * step;
    const hiY = Math.ceil ((viewCY + viewRange) / step) * step;
    for (let v = loY; v <= hiY; v += step) {
      lines.push({ vertical: false, v });
    }
    return lines;
  })();

  // ── Current LIDAR scan transformed to world frame ─────────────────────────
  $: worldScan = (() => {
    const pose = $mapPose;
    const scan = $robotState?.lidar;
    if (!pose || !scan?.length) return [];
    const { x, y, heading } = pose;
    return scan.map(([angle, dist]) => {
      const rad = (heading + angle) * Math.PI / 180;
      return [x + dist * Math.sin(rad), y + dist * Math.cos(rad)];
    });
  })();

  // ── Controls ───────────────────────────────────────────────────────────────
  function fit() {
    const pts = $mapPoints;
    if (!pts.length) { viewCX = 0; viewCY = 0; viewRange = 300; return; }
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of pts) {
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
    }
    const pose = $mapPose;
    if (pose) {
      if (pose.x < minX) minX = pose.x; if (pose.x > maxX) maxX = pose.x;
      if (pose.y < minY) minY = pose.y; if (pose.y > maxY) maxY = pose.y;
    }
    viewCX    = (minX + maxX) / 2;
    viewCY    = (minY + maxY) / 2;
    viewRange = Math.max((maxX - minX) / 2, (maxY - minY) / 2) * 1.2 + 50;
  }

  function zoomIn()  { viewRange = Math.max(50,    viewRange / 1.5); }
  function zoomOut() { viewRange = Math.min(20000, viewRange * 1.5); }

  function doClearMap() {
    clearMap();
    send({ cmd: 'clear_map' });
  }

  // ── Robot pose arrow ───────────────────────────────────────────────────────
  function poseArrowPath(pose, size) {
    const { x, y, heading } = pose;
    const h = heading * Math.PI / 180;
    const tip  = [x + size * Math.sin(h),       -(y + size * Math.cos(h))];
    const left = [x + size * 0.5 * Math.sin(h + 2.3), -(y + size * 0.5 * Math.cos(h + 2.3))];
    const rite = [x + size * 0.5 * Math.sin(h - 2.3), -(y + size * 0.5 * Math.cos(h - 2.3))];
    return `M ${tip[0]} ${tip[1]} L ${left[0]} ${left[1]} L ${rite[0]} ${rite[1]} Z`;
  }

  $: arrowSize = viewRange * 0.06;
  $: dotR      = Math.max(1, viewRange * 0.008);
  $: scanDotR  = Math.max(1, viewRange * 0.006);
</script>

<div class="flex flex-col h-full bg-[#161920] text-slate-200 overflow-hidden">

  <!-- ── Header ── -->
  <div class="flex items-center gap-2 px-4 py-2 border-b border-[#2e3340] bg-[#1a1d26] flex-shrink-0">
    <svg class="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0"/>
      <path d="M12 8v4l3 3"/>
      <path d="M12 3v1M12 20v1M3 12H2M22 12h-1"/>
    </svg>
    <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">Map</span>

    <div class="flex items-center gap-1.5 text-[11px] text-slate-500 ml-2">
      <span class="w-2 h-2 rounded-full bg-teal-500 inline-block"></span>
      {$mapPoints.length.toLocaleString()} points
      {#if $mapPose}
        <span class="ml-2">
          pose ({$mapPose.x.toFixed(0)}, {$mapPose.y.toFixed(0)}) {$mapPose.heading.toFixed(0)}°
        </span>
      {/if}
    </div>

    <div class="ml-auto flex items-center gap-1.5">
      <!-- Zoom controls -->
      <button class="px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340]
                     text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
              on:click={zoomIn}>+</button>
      <button class="px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340]
                     text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
              on:click={zoomOut}>−</button>
      <button class="px-2.5 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340]
                     text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
              on:click={fit}>Fit</button>

      <!-- Clear -->
      <button class="px-2.5 py-1 rounded text-xs bg-red-900/20 border border-red-700/30
                     text-red-400 hover:bg-red-800/30 hover:border-red-600/50 transition-colors"
              on:click={doClearMap}>Clear</button>

      <!-- Robot shape toggle -->
      <button class="px-2.5 py-1 rounded text-xs border transition-colors
                     {showShapePanel
                       ? 'bg-amber-600/20 border-amber-500/50 text-amber-300'
                       : 'bg-[#1e2129] border-[#2e3340] text-slate-400 hover:text-slate-200 hover:border-slate-500'}"
              on:click={() => showShapePanel = !showShapePanel}>
        Robot shape
      </button>
    </div>

    <!-- Grid step label -->
    <span class="text-[10px] text-slate-700 ml-2">grid {step >= 100 ? step/100 + ' m' : step + ' cm'}</span>
  </div>

  <!-- ── Robot shape panel ── -->
  {#if showShapePanel}
    <div class="flex-shrink-0 border-b border-[#2e3340] bg-[#14171f] px-4 py-3">
      <div class="flex flex-wrap gap-4 items-start">

        <!-- Add rectangle form -->
        <div class="flex flex-col gap-2">
          <span class="text-[10px] text-amber-500 uppercase tracking-widest">Add rectangle</span>
          <div class="flex flex-wrap gap-2 items-end">
            <label class="flex flex-col gap-0.5">
              <span class="text-[9px] text-slate-600 uppercase">Label</span>
              <input type="text" bind:value={newLabel} placeholder="e.g. body"
                class="w-20 px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340] text-slate-300" />
            </label>
            <label class="flex flex-col gap-0.5">
              <span class="text-[9px] text-slate-600 uppercase">W (cm)</span>
              <input type="number" bind:value={newW} min="1" max="500"
                class="w-16 px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340] text-slate-300 text-center" />
            </label>
            <label class="flex flex-col gap-0.5">
              <span class="text-[9px] text-slate-600 uppercase">H (cm)</span>
              <input type="number" bind:value={newH} min="1" max="500"
                class="w-16 px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340] text-slate-300 text-center" />
            </label>
            <label class="flex flex-col gap-0.5">
              <span class="text-[9px] text-slate-600 uppercase">X off</span>
              <input type="number" bind:value={newX} step="0.5"
                class="w-16 px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340] text-slate-300 text-center" />
            </label>
            <label class="flex flex-col gap-0.5">
              <span class="text-[9px] text-slate-600 uppercase">Y off</span>
              <input type="number" bind:value={newY} step="0.5"
                class="w-16 px-2 py-1 rounded text-xs bg-[#1e2129] border border-[#2e3340] text-slate-300 text-center" />
            </label>
            <button class="px-3 py-1 rounded text-xs bg-amber-600/20 border border-amber-500/50
                           text-amber-300 hover:bg-amber-600/35 transition-colors self-end"
                    on:click={addRect}>Add</button>
          </div>
          <p class="text-[9px] text-slate-700">X off: +right / −left from centre &nbsp;·&nbsp; Y off: +forward / −back</p>
        </div>

        <!-- Existing rectangles list -->
        {#if $robotShapeRects.length > 0}
          <div class="flex flex-col gap-1">
            <span class="text-[10px] text-amber-500 uppercase tracking-widest">Rectangles</span>
            {#each $robotShapeRects as r}
              <div class="flex items-center gap-2 text-[11px] text-slate-400">
                <span class="font-semibold text-amber-400">{r.label}</span>
                <span>{r.width}×{r.height} cm</span>
                {#if r.x !== 0 || r.y !== 0}
                  <span class="text-slate-600">at ({r.x > 0 ? '+' : ''}{r.x}, {r.y > 0 ? '+' : ''}{r.y})</span>
                {/if}
                <button class="text-slate-700 hover:text-red-400 transition-colors ml-1"
                        on:click={() => deleteRect(r.id)}>✕</button>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- ── Map canvas ── -->
  {#if $mapPoints.length === 0 && !$mapPose}
    <div class="flex-1 flex flex-col items-center justify-center gap-3 text-slate-700">
      <svg class="w-16 h-16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <path d="M3 7l4-4 10 5 4-4v14l-4 4-10-5-4 4V7z"/>
        <line x1="7" y1="3" x2="7" y2="17"/>
        <line x1="17" y1="8" x2="17" y2="22"/>
      </svg>
      <p class="text-sm">No map data yet</p>
      <p class="text-xs text-slate-800 text-center max-w-xs">
        Call <code class="text-slate-600">robot.map_points()</code> and
        <code class="text-slate-600">robot.map_pose()</code> from student code to build the map.
      </p>
    </div>
  {:else}
    <svg class="flex-1 min-h-0 w-full" viewBox={viewBox} preserveAspectRatio="xMidYMid meet"
         style="background:#0d1117;">

      <!-- Grid lines -->
      {#each gridLines as gl}
        {#if gl.vertical}
          <line x1={gl.v} y1={-(viewCY + viewRange)} x2={gl.v} y2={-(viewCY - viewRange)}
                stroke={gl.v === 0 ? '#2a5a3a' : '#1a2a1a'} stroke-width={viewRange * 0.002} />
        {:else}
          <line x1={viewCX - viewRange} y1={-gl.v} x2={viewCX + viewRange} y2={-gl.v}
                stroke={gl.v === 0 ? '#2a5a3a' : '#1a2a1a'} stroke-width={viewRange * 0.002} />
        {/if}
      {/each}

      <!-- Accumulated obstacle points (pushed by student code) -->
      {#each $mapPoints as [x, y]}
        <circle cx={x} cy={-y} r={dotR} fill="#4ade80" opacity="0.7" />
      {/each}

      <!-- Current LIDAR scan in world frame (lighter, shown when pose is known) -->
      {#each worldScan as [x, y]}
        <circle cx={x} cy={-y} r={scanDotR} fill="#67e8f9" opacity="0.5" />
      {/each}

      <!-- Robot shape rectangles (rendered at pose, or at origin if no pose) -->
      {#if $robotShapeRects.length > 0}
        <g transform={shapeTransform}>
          {#each $robotShapeRects as r}
            <!--
              In robot frame: x=right, y=forward.
              In SVG group (after y-flip in shapeTransform): SVG y = -world y.
              So rect top-left in SVG = (x - w/2, -(y + h/2))
            -->
            <rect
              x={r.x - r.width  / 2}
              y={-(r.y + r.height / 2)}
              width={r.width}
              height={r.height}
              fill="rgba(251,191,36,0.07)"
              stroke="#fbbf24"
              stroke-width={Math.max(0.5, viewRange * 0.003)}
              stroke-dasharray="{viewRange * 0.015} {viewRange * 0.008}"
              opacity="0.8"
              rx={viewRange * 0.005}
            />
          {/each}
          <!-- Centre crosshair -->
          <circle cx="0" cy="0" r={arrowSize * 0.25} fill="#fbbf24" opacity="0.5" />
        </g>
      {/if}

      <!-- Robot pose indicator -->
      {#if $mapPose}
        <!-- Trail dot at robot position -->
        <circle cx={$mapPose.x} cy={-$mapPose.y} r={arrowSize * 0.4}
                fill="#fbbf24" opacity="0.9" />
        <!-- Heading arrow -->
        <path d={poseArrowPath($mapPose, arrowSize)} fill="#fbbf24" opacity="0.95" />
      {/if}

      <!-- Origin marker -->
      <circle cx="0" cy="0" r={dotR * 1.5} fill="#6366f1" opacity="0.8" />
    </svg>
  {/if}

</div>

<!-- Legend -->
<div class="flex items-center gap-4 px-4 py-1.5 border-t border-[#2e3340] bg-[#1a1d26]
            flex-shrink-0 text-[10px] text-slate-600">
  <span class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-[#4ade80] inline-block opacity-70"></span>
    Accumulated obstacles
  </span>
  <span class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-[#67e8f9] inline-block opacity-50"></span>
    Current scan
  </span>
  <span class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-[#fbbf24] inline-block"></span>
    Robot pose
  </span>
  <span class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-[#6366f1] inline-block opacity-80"></span>
    Origin (0, 0)
  </span>
</div>
