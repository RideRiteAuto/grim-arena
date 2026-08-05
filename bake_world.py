#!/usr/bin/env python3
"""Bake "Asterra World Map v2.html" into the runtime world data.

The map SVG is the source of truth for the world: coastlines, zones,
mountains, rivers, roads, and settlement sites are all parsed straight out of
the drawing, rasterized, turned into an elevation model, and packed into
`worldgen-data.js` (base64 + deflate). repack.py injects that file plus
`worldgen.js` into the game bundle between the WORLD-GEN markers.

Run by hand after any map change:  python3 bake_world.py
Also writes /tmp/world-preview.png so a human can eyeball the result against
the map before shipping. Deterministic: same map in, same bytes out.

Coordinates: map pixels (1650x1000, y down) -> world meters at 4 m/px,
recentered so THE CAPITAL (map 598,506) is world origin. world_x = (px-598)*4,
world_z = (py-506)*4. Sea level is world y = 0.
"""
import base64
import io
import json
import re
import zlib

import numpy as np

MAP_FILE = 'Asterra World Map v2.html'
OUT_JS = 'worldgen-data.js'
PREVIEW = '/tmp/world-preview.png'

MAP_W, MAP_H = 1650, 1000
M_PER_PX = 4.0
ORIGIN = (598.0, 506.0)          # capital site -> world (0,0)
G = 2                            # bake grid: 2 map px per cell = 8 m
GW, GH = MAP_W // G, MAP_H // G  # 825 x 500

# Zone ids. 0 stays "open sea"; keep these stable forever once shipped.
ZONES = [
    ('SEA',        None,      dict(base=0.0,  rough=0.0)),
    ('FROSTWILD',  '#dfe4e2', dict(base=14.0, rough=3.2)),
    ('IRONSPIRE',  '#d3c8ac', dict(base=30.0, rough=5.0)),
    ('HEARTLANDS', '#e4d9ae', dict(base=7.0,  rough=1.6)),
    ('GREENWOOD',  '#c9d3ab', dict(base=11.0, rough=2.6)),
    ('SUNCOAST',   '#ecd9a4', dict(base=5.0,  rough=1.4)),
    ('WINDSCAR',   '#d9d2a4', dict(base=12.0, rough=1.8)),
    ('EMBER',      '#ddbfa6', dict(base=32.0, rough=5.2)),
    ('EMBER_HI',   '#d4ab8b', dict(base=40.0, rough=5.6)),   # inner highlands
    ('MISTFEN',    '#c3ceb4', dict(base=2.2,  rough=0.7)),
    ('SUNSCORCH',  '#e5c493', dict(base=8.0,  rough=2.2)),
    ('EASTRIDGE',  '#d9d6cc', dict(base=26.0, rough=4.0)),   # uncharted frost ridge
    ('ISLES',      None,      dict(base=6.0,  rough=2.0)),   # land with no zone overlay
]
ZONE_ID = {name: i for i, (name, _, _p) in enumerate(ZONES)}
COLOR2ZONE = {c: i for i, (_n, c, _p) in enumerate(ZONES) if c}

MOUNTAIN_AMP = {'mtn': 46.0, 'mtn-ember': 44.0, 'mtn-frost': 34.0}
MOUNTAIN_SIGMA_PX = 26.0         # gaussian radius per peak glyph, map px

# Anchor names by map coordinate (from the map's label layer).
ANCHORS = [
    ('capital', 'THE CAPITAL',     598, 506),
    ('town',    'Ironspire Hold',  340, 432),
    ('town',    'Frostwatch',      448, 258),
    ('town',    'Timberdown',      340, 662),
    ('town',    'Ember Hold',     1256, 452),
    ('town',    'Windscar Post',  1000, 420),
    ('town',    'Duskwell Oasis', 1298, 762),
    ('port',    'Suncoast Harbor', 497, 789),
    ('port',    'Frosthaven',      618, 291),
    ('port',    'Ashport',        1103, 306),
    ('port',    'Fenmouth',        995, 719),
    ('port',    'Driftwatch Isle', 827, 260),
    ('choke',   'Highpass',        452, 430),
    ('choke',   'Frost Gate',      528, 338),
    ('choke',   'Ember Gap',      1164, 544),
    ('choke',   'The Narrows',     846, 672),
    ('bridge',  'Argent Bridge',   480, 415),
    ('bridge',  'Kingsford Bridge', 525, 600),
]

# ---------------------------------------------------------------- svg parsing

def parse_d(d):
    """M/L/Z absolute polyline -> Nx2 float array (the map only uses these)."""
    pts = re.findall(r'[-\d.]+,[-\d.]+', d)
    return np.array([[float(a) for a in p.split(',')] for p in pts])


def load_map():
    html = io.open(MAP_FILE, encoding='utf-8').read()
    svg = html[html.index('<svg'):html.index('</svg>')]

    def attrs(tag):
        return dict(re.findall(r'([\w:-]+)="([^"]*)"', tag))

    # The Drive map names its geometry: land* / isle* are landmasses, t_* are
    # zone territories. Rivers and the lake are the #a3bfc2-filled paths.
    T_ZONE = {'t_frostwild': 'FROSTWILD', 't_ironspire': 'IRONSPIRE',
              't_heart': 'HEARTLANDS', 't_greenwood': 'GREENWOOD',
              't_suncoast': 'SUNCOAST', 't_steppe': 'WINDSCAR',
              't_ember': 'EMBER', 't_mistfen': 'MISTFEN',
              't_barrens': 'SUNSCORCH'}
    land, zones, water, roads = [], [], [], []
    seen_water = set()
    for m in re.finditer(r'<path\b[^>]*>', svg):
        a = attrs(m.group(0))
        d, pid, fill = a.get('d', ''), a.get('id', ''), a.get('fill', '')
        stroke = a.get('stroke', '')
        if not d:
            continue
        if pid.startswith('land') or pid.startswith('isle'):
            land.append(parse_d(d))
        elif pid in T_ZONE:
            zones.append((ZONE_ID[T_ZONE[pid]], parse_d(d)))
        elif fill == '#a3bfc2' and stroke in ('#5f8489', '#37301f'):
            key = d[:80]
            if key not in seen_water:                  # lake is drawn twice
                seen_water.add(key)
                water.append(parse_d(d))

    peaks = []
    for m in re.finditer(r'<use href="#(mtn[\w-]*)" transform="translate\(([\d.]+),([\d.]+)\)(?: scale\(([\d.]+)\))?"', svg):
        kind, x, y, s = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4) or 1.0)
        peaks.append((kind, x, y, s))

    road_g = re.search(r'<g fill="none" stroke="#8a6f4d"[^>]*>(.*?)</g>', svg, re.S)
    if road_g:
        for m in re.finditer(r'<path d="([^"]+)"', road_g.group(1)):
            roads.append(parse_d(m.group(1)))
    return land, zones, water, peaks, roads


# ------------------------------------------------------------- rasterization

def rasterize(polys, w, h, scale):
    """Even-odd scanline fill of map-px polygons onto a w*h grid."""
    grid = np.zeros((h, w), dtype=bool)
    for poly in polys if isinstance(polys, list) else [polys]:
        p = np.asarray(poly) / scale
        ys = p[:, 1]
        y0, y1 = max(0, int(ys.min())), min(h - 1, int(ys.max()) + 1)
        x1s, y1s = p[:, 0], p[:, 1]
        x2s, y2s = np.roll(x1s, -1), np.roll(y1s, -1)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            hit = (y1s <= yc) != (y2s <= yc)
            if not hit.any():
                continue
            t = (yc - y1s[hit]) / (y2s[hit] - y1s[hit])
            xs = np.sort(x1s[hit] + t * (x2s[hit] - x1s[hit]))
            for i in range(0, len(xs) - 1, 2):
                xa, xb = int(np.ceil(xs[i] - 0.5)), int(np.floor(xs[i + 1] - 0.5))
                if xb >= xa:
                    grid[yy, max(0, xa):min(w, xb + 1)] = True
    return grid


def distance_px(mask):
    """Approximate euclidean distance (in cells) to the True set, via 2-pass chamfer."""
    INF = 1e6
    d = np.where(mask, 0.0, INF)
    h, w = d.shape
    for y in range(h):
        row = d[y]
        up = d[y - 1] if y else None
        for x in range(w):
            v = row[x]
            if x:
                v = min(v, row[x - 1] + 1)
            if up is not None:
                v = min(v, up[x] + 1)
                if x:
                    v = min(v, up[x - 1] + 1.4142)
                if x + 1 < w:
                    v = min(v, up[x + 1] + 1.4142)
            row[x] = v
    for y in range(h - 1, -1, -1):
        row = d[y]
        dn = d[y + 1] if y + 1 < h else None
        for x in range(w - 1, -1, -1):
            v = row[x]
            if x + 1 < w:
                v = min(v, row[x + 1] + 1)
            if dn is not None:
                v = min(v, dn[x] + 1)
                if x + 1 < w:
                    v = min(v, dn[x + 1] + 1.4142)
                if x:
                    v = min(v, dn[x - 1] + 1.4142)
            row[x] = v
    return d


def find_crossings(roads, water_polys):
    """Where every trade route crosses water, and how wide the gap is.

    The map draws exactly two bridge glyphs, Argent and Kingsford, but the
    eight routes cross water in a lot more places than that. Rather than
    hand-listing them, walk each road over a rasterized water mask and record
    every entry-to-exit run.

    The hard part is telling a real crossing from a road that merely HUGS a
    shoreline: both look like "road goes in, road comes out". The test is the
    width of the water measured through the crossing midpoint in every
    direction. At a genuine crossing the road's run through the water is close
    to the NARROWEST way across; a road running along a lake edge clips a
    sliver whose along-road length is far longer than the shortest span
    through the same point. Anything more than ~2.2x the minimum is running
    beside the water, not over it, and is dropped.

    Deliberately does NOT touch elevation. Flattening terrain at ten new sites
    would change the baked heights, which would move every procedurally placed
    prop in the world. The bridge geometry fits the land instead.
    """
    SUBPX = 3.0                       # samples per map px along the road
    FORD_M = 6.0                      # narrower than this, wade it
    SHORE_RATIO = 2.2                 # along-road / minimum span reject limit

    mask = rasterize(water_polys, MAP_W, MAP_H, 1)

    def wet(px, py):
        ix, iy = int(px), int(py)
        return 0 <= ix < MAP_W and 0 <= iy < MAP_H and mask[iy, ix]

    def span_through(px, py, ang):
        """Water extent through a point along one direction, in map px."""
        dx, dy = np.cos(ang), np.sin(ang)
        out = 0.0
        for s in (1, -1):
            t = 0.0
            while t < 220:
                t += 0.5
                if not wet(px + dx * s * t, py + dy * s * t):
                    break
            out += t
        return out

    out = []
    for ri, r in enumerate(roads):
        inw, start = False, None
        for j in range(len(r) - 1):
            a, b = r[j], r[j + 1]
            n = max(2, int(np.hypot(*(b - a)) * SUBPX))
            for t in np.linspace(0, 1, n):
                p = a + (b - a) * t
                w = wet(p[0], p[1])
                if w and not inw:
                    inw, start = True, p
                elif not w and inw:
                    inw = False
                    mid = (start + p) / 2.0
                    along_px = float(np.hypot(*(p - start)))
                    along_m = along_px * M_PER_PX
                    if along_m < FORD_M:
                        continue
                    narrow_px = min(span_through(mid[0], mid[1], k * np.pi / 12.0)
                                    for k in range(12))
                    narrow_m = narrow_px * M_PER_PX
                    # Shore-hugging only counts as a false positive when the
                    # water at that point is genuinely a sliver. A wide river
                    # mouth crossed at an angle also scores a high ratio, and
                    # that is a real crossing that needs a real structure.
                    if narrow_m < 40.0 and along_px > narrow_px * SHORE_RATIO:
                        continue                       # running along the bank
                    d = p - start
                    out.append(dict(
                        road=ri,
                        x=round((mid[0] - ORIGIN[0]) * M_PER_PX, 1),
                        z=round((mid[1] - ORIGIN[1]) * M_PER_PX, 1),
                        heading=round(float(np.arctan2(d[0], d[1])), 4),
                        span=round(along_m, 1),
                        kind='causeway' if along_m > 80 else 'trestle'))
    # Two spans that land on top of each other are one bridge drawn twice.
    keep = []
    for b in out:
        if any((b['x'] - k['x']) ** 2 + (b['z'] - k['z']) ** 2 < 60.0 ** 2 for k in keep):
            continue
        keep.append(b)
    # The map's own two glyphs win their names; the rest are generated.
    named = {'Argent Bridge': (480, 415), 'Kingsford Bridge': (525, 600)}
    for nm, (px, py) in named.items():
        wx, wz = (px - ORIGIN[0]) * M_PER_PX, (py - ORIGIN[1]) * M_PER_PX
        best, bd = None, 1e9
        for b in keep:
            d = (b['x'] - wx) ** 2 + (b['z'] - wz) ** 2
            if d < bd:
                bd, best = d, b
        if best is not None and bd < 140.0 ** 2:
            best['name'] = nm
    for i, b in enumerate(keep):
        b.setdefault('name', 'Crossing %d' % (i + 1))
    return keep


def blur(a, n=1):
    for _ in range(n):
        p = np.pad(a, 1, mode='edge')
        a = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + p[1:-1, 1:-1] * 4) / 8.0
    return a


# ---------------------------------------------------------------- the bake

def main():
    land_p, zone_p, water_p, peaks, roads = load_map()
    print('parsed: %d land, %d zone, %d water polys, %d peaks, %d roads'
          % (len(land_p), len(zone_p), len(water_p), len(peaks), len(roads)))

    land = rasterize(land_p, GW, GH, G)
    water = rasterize(water_p, GW, GH, G)
    zone = np.zeros((GH, GW), dtype=np.uint8)
    for zid, poly in zone_p:
        zone[rasterize(poly, GW, GH, G)] = zid
    # land with no overlay: islands or gaps -> nearest painted zone, else ISLES
    unpainted = land & (zone == 0)
    if unpainted.any():
        painted = zone.copy()
        for _ in range(40):  # BFS dilate zone ids over gaps
            grow = unpainted & (painted == 0)
            if not grow.any():
                break
            p = np.pad(painted, 1, mode='edge')
            for sh in (p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]):
                fill = grow & (painted == 0) & (sh > 0)
                painted[fill] = sh[fill]
        painted[unpainted & (painted == 0)] = ZONE_ID['ISLES']
        zone[unpainted] = painted[unpainted]
    zone[~land] = 0

    coast = distance_px(~land)          # distance to sea, in cells (8 m each)
    coast_in = distance_px(land)        # distance to land, for sea depth
    wdist = distance_px(water)          # distance to river/lake water

    # --- elevation, in meters ------------------------------------------------
    base = np.zeros((GH, GW))
    rough = np.zeros((GH, GW))
    for i, (_n, _c, p) in enumerate(ZONES):
        sel = zone == i
        base[sel] = p['base']
        rough[sel] = p['rough']
    inland = np.clip(coast / (48.0 / (G * M_PER_PX / 2)), 0, 1)   # full base ~48m*4 inland
    inland = np.clip(coast * (G * M_PER_PX) / 220.0, 0, 1)        # ramp over ~220 m
    elev = base * (inland ** 1.2) * 1.0
    elev = blur(elev, 3)

    yy, xx = np.mgrid[0:GH, 0:GW]
    for kind, px, py, s in peaks:
        sig = (MOUNTAIN_SIGMA_PX * s) / G
        amp = MOUNTAIN_AMP[kind] * s
        d2 = (xx - px / G) ** 2 + (yy - py / G) ** 2
        elev += amp * np.exp(-d2 / (2 * sig * sig))
    elev = blur(elev, 2)
    elev = 95.0 * np.tanh(elev / 95.0)   # soft cap: stacked peaks stay ~90 m
    elev *= np.where(land, 1.0, 0.0)

    # Shore profile from a smooth SIGNED distance to the coastline. Gentle
    # 10cm/m beach slope inland, 16cm/m into the sea, blending to the interior
    # elevation and the deep floor over ~80m. This is what makes coastlines
    # smooth curves with wadeable beaches instead of stair-stepped cliffs.
    wpx = G * M_PER_PX
    sd = blur((coast - coast_in) * wpx, 2)          # meters, + inland, - at sea
    shore = np.where(sd >= 0, np.minimum(sd * 0.10, 6.0), np.maximum(sd * 0.16, -26.0))
    w_in = np.clip((sd - 8.0) / 80.0, 0, 1); w_in = w_in * w_in * (3 - 2 * w_in)
    w_out = np.clip((-sd - 8.0) / 80.0, 0, 1); w_out = w_out * w_out * (3 - 2 * w_out)
    interior = np.maximum(elev * inland ** 0.5, shore)
    deep = -np.clip(coast_in * wpx / 110.0, 0, 1) * 26.0 - 1.2
    elev = np.where(sd >= 0, shore * (1 - w_in) + interior * w_in,
                             shore * (1 - w_out) + np.minimum(deep, shore) * w_out)

    # rivers and the lake carve below sea level; banks ease down within ~24 m
    wm = (G * M_PER_PX)
    carve_t = np.clip(1.0 - (wdist * wm) / 24.0, 0, 1)
    river_bed = np.where(water, -3.4, np.minimum(elev, 1.0))
    elev = elev * (1 - carve_t ** 2) + river_bed * carve_t ** 2
    elev[water] = np.minimum(elev[water], -2.6)

    # flatten around anchors so towns and gates sit on buildable ground
    for kind, name, ax, ay in ANCHORS:
        if kind in ('choke',):
            r0, r1, target = 8, 16, None      # smooth the pass, keep its height
        elif kind == 'capital':
            # Big plateau at exactly 0: the old town (arena floor, buildings)
            # was built assuming ground = 0 at the origin. Sea renders at
            # -0.06 so the plateau never z-fights the water plane.
            r0, r1, target = 24, 44, 0.0
        elif kind == 'bridge':
            r0, r1, target = 5, 12, None
        else:
            r0, r1, target = 12, 26, None
        cx, cz = ax / G, ay / G
        d = np.sqrt((xx - cx) ** 2 + (yy - cz) ** 2)
        t = np.clip((r1 - d) / (r1 - r0), 0, 1) ** 2
        area = d < r1
        if not area.any():
            continue
        tv = target if target is not None else float(np.median(elev[d < r0]))
        if kind == 'port':
            tv = max(1.0, min(tv, 2.4))       # ports stay near the waterline
        # flatten LAND only — the sea floor around a harbor stays sea
        elev = np.where(land, elev * (1 - t) + tv * t, elev)
        keep_water = water & area
        elev[keep_water] = np.minimum(elev[keep_water], -2.6)

    # roads gently relax terrain toward a rolling average along their line
    road_mask = np.zeros((GH, GW), dtype=bool)
    for r in roads:
        for i in range(len(r) - 1):
            a, b = r[i] / G, r[i + 1] / G
            n = max(2, int(np.hypot(*(b - a)) * 2))
            for t in np.linspace(0, 1, n):
                x, y = a + (b - a) * t
                if 0 <= int(y) < GH and 0 <= int(x) < GW:
                    road_mask[int(y), int(x)] = True
    rdist = distance_px(road_mask)
    rt = np.clip(1.0 - (rdist * wm) / 18.0, 0, 1) * 0.55
    elev = elev * (1 - rt) + blur(elev, 2) * rt

    # --- quantize + pack -----------------------------------------------------
    q = np.clip((elev + 40.0) * 2.0, 0, 255).astype(np.uint8)   # 0.5 m steps, -40..87.5
    zq = zone.astype(np.uint8)

    def pack(arr):
        return base64.b64encode(zlib.compress(arr.tobytes(), 9)).decode()

    world_anchors = [
        dict(kind=k, name=n,
             x=round((ax - ORIGIN[0]) * M_PER_PX, 1),
             z=round((ay - ORIGIN[1]) * M_PER_PX, 1))
        for k, n, ax, ay in ANCHORS
    ]

    # The trade routes, in world metres. These are the SAME polylines already
    # used above to relax terrain along the roads, so what the player walks on
    # and what the ground was smoothed for can never disagree.
    #
    # The map's own vertices are exported, not a resampling: 170 points across
    # all 8 routes, versus ~2,400 if resampled to 4 m. The runtime smooths with
    # a Catmull-Rom pass, which gives a better curve than dense linear points
    # and keeps the data file small. Map pixel -> world metre uses the same
    # transform as everything else here, so the roads are pixel accurate to the
    # drawing by construction rather than by eyeballing.
    world_roads = [
        [[round((px - ORIGIN[0]) * M_PER_PX, 1),
          round((py - ORIGIN[1]) * M_PER_PX, 1)] for px, py in r]
        for r in roads
    ]
    _rn = sum(len(r) for r in world_roads)
    _rl = sum(float(np.hypot(*(r[i + 1] - r[i]))) * M_PER_PX
              for r in roads for i in range(len(r) - 1))
    print('roads: %d routes, %d points, %.2f km' % (len(world_roads), _rn, _rl / 1000))

    world_bridges = find_crossings(roads, water_p)
    print('bridges: %d spans, widest %.0f m'
          % (len(world_bridges), max([b['span'] for b in world_bridges] or [0])))
    meta = dict(GW=GW, GH=GH, CELL=G * M_PER_PX, M_PER_PX=M_PER_PX,
                ORIGIN=list(ORIGIN), MAP_W=MAP_W, MAP_H=MAP_H,
                ELEV_OFF=-40.0, ELEV_SCALE=0.5, GEN_V=1)
    js = (
        '// GENERATED by bake_world.py from "Asterra World Map v2.html" — do not edit.\n'
        '// Layers: elevation (u8, 0.5m steps from -40m) and zone id, 825x500 cells\n'
        '// at 8m per cell, deflate+base64. Decoded once at boot by worldgen.js.\n'
        '// WG_ROADS: the map trade routes as world-metre polylines, map order.\n'
        'const WG_META = ' + json.dumps(meta) + ';\n'
        'const WG_ANCHORS = ' + json.dumps(world_anchors) + ';\n'
        'const WG_ZONES = ' + json.dumps([z[0] for z in ZONES]) + ';\n'
        'const WG_ROADS = ' + json.dumps(world_roads) + ';\n'
        'const WG_BRIDGES = ' + json.dumps(world_bridges) + ';\n'
        "const WG_ELEV_B64 = '" + pack(q) + "';\n"
        "const WG_ZONE_B64 = '" + pack(zq) + "';\n"
    )
    io.open(OUT_JS, 'w', encoding='utf-8').write(js)
    print('wrote %s (%d KB)' % (OUT_JS, len(js) // 1024))

    # --- preview -------------------------------------------------------------
    try:
        from PIL import Image
        img = np.zeros((GH, GW, 3), dtype=np.uint8)
        deep = elev < -8; shal = (elev >= -8) & (elev < 0)
        img[deep] = (60, 96, 116); img[shal] = (110, 150, 160)
        pal = {
            'FROSTWILD': (223, 228, 226), 'IRONSPIRE': (150, 138, 112),
            'HEARTLANDS': (168, 180, 110), 'GREENWOOD': (110, 140, 90),
            'SUNCOAST': (214, 196, 140), 'WINDSCAR': (190, 182, 120),
            'EMBER': (170, 120, 95), 'EMBER_HI': (150, 100, 80),
            'MISTFEN': (120, 145, 110), 'SUNSCORCH': (222, 186, 120),
            'EASTRIDGE': (180, 180, 175), 'ISLES': (200, 185, 150), 'SEA': (0, 0, 0),
        }
        for i, (n, _c, _p) in enumerate(ZONES):
            sel = (zone == i) & (elev >= 0)
            img[sel] = pal[n]
        sh = np.clip((elev / 60.0), 0, 1)[..., None]
        img = np.where(elev[..., None] >= 0,
                       (img * (0.72 + 0.55 * sh)).clip(0, 255), img).astype(np.uint8)
        for k, n, ax, ay in ANCHORS:
            x, y = int(ax / G), int(ay / G)
            img[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = (200, 30, 30)
        Image.fromarray(img).resize((GW, GH)).save(PREVIEW)
        print('preview ->', PREVIEW)
    except Exception as e:
        print('preview skipped:', e)

    print('elev range %.1f .. %.1f m, land %.0f%%, water(rivers) %.1f%%'
          % (elev.min(), elev.max(), 100 * land.mean(), 100 * water.mean()))


if __name__ == '__main__':
    main()
