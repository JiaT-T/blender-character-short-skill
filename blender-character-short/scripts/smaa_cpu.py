"""NumPy translation of the three SMAA passes in Huaxu C69G59uD2.js.

Prototype, not yet GPU-equivalent: see README.md and evidence reports.
Public arrays are top-down HxWx4 float32, display-encoded, premultiplied RGBA.
Input is the website's composite RGBA8 result, NOT linear beauty/straight RGB.
Area/Search paths are REQUIRED. No third-party image is embedded in this module.
The shader's unusual float(ivec2) offset and Y search signs are intentional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

SOURCE_SHA256 = '172188ea0193106745299323b5b2e2ac9cc8b7d33535e6d538798b1685dd8d9e'
F = np.float32


def sample_linear(image, uv):
    """GL LINEAR + CLAMP_TO_EDGE. Row zero of internal arrays is texture v=0."""
    h, w = image.shape[:2]
    p = np.asarray(uv, dtype=np.float32) * np.array([w, h], dtype=np.float32) - F(.5)
    lo = np.floor(p).astype(np.int32)
    f = p - lo
    x0 = np.clip(lo[..., 0], 0, w-1)
    x1 = np.clip(lo[..., 0]+1, 0, w-1)
    y0 = np.clip(lo[..., 1], 0, h-1)
    y1 = np.clip(lo[..., 1]+1, 0, h-1)
    fx, fy = f[..., 0:1].astype(np.float32), f[..., 1:2].astype(np.float32)
    a = image[y0, x0] * (F(1)-fx) + image[y0, x1] * fx
    b = image[y1, x0] * (F(1)-fx) + image[y1, x1] * fx
    return (a*(F(1)-fy)+b*fy).astype(np.float32)


def sample_nearest(image, uv):
    h, w = image.shape[:2]
    p = np.floor(np.asarray(uv, dtype=np.float32)*np.array([w, h], dtype=np.float32)).astype(np.int32)
    return image[np.clip(p[..., 1], 0, h-1), np.clip(p[..., 0], 0, w-1)]


def neighbor(image, dx, dy):
    """Internal bottom-up array, positive dy means positive UV y."""
    h, w = image.shape[:2]
    return image[np.clip(np.arange(h)+dy, 0, h-1)[:, None],
                 np.clip(np.arange(w)+dx, 0, w-1)[None, :]]


def half_target(x):
    return np.asarray(x, dtype=np.float16).astype(np.float32)


def unorm8_target(x):
    # Exact half-LSB tie behavior may depend on GL implementation; not claimed.
    return (np.floor(np.clip(x, 0, 1)*F(255)+F(.5))/F(255)).astype(np.float32)


def load_tables(area_path, search_path):
    """PNG scanline 0 stays v=0: source textures explicitly use flipY=false."""
    area = np.asarray(Image.open(area_path).convert('RGBA'), dtype=np.float32)/F(255)
    search = np.asarray(Image.open(search_path).convert('RGBA'), dtype=np.float32)/F(255)
    if area.shape[:2] != (560, 160) or search.shape[:2] != (33, 66):
        raise ValueError(f'Source SMAA lookup dimensions required: area 160x560, search 66x33; got {area.shape}, {search.shape}')
    return area, search


def edge_pass(color, threshold=.1, previous_edges=None):
    """Bo + ds/ss runtime rewrite; see source-manifest.json for exact anchors.

    Website edges use RGB composited over 0.5 gray, not stock SMAA RGB alone.
    This patch is also present in captured GPU program8. Internal bottom-up.
    """
    rgb = color[..., :3] + F(.5)*(F(1)-color[..., 3:4])
    delta = lambda dx, dy: np.max(np.abs(rgb-neighbor(rgb, dx, dy)), axis=-1)
    left, top = delta(-1, 0), delta(0, 1)
    maximum = np.maximum.reduce([left, top, delta(1, 0), delta(0, -1), delta(-2, 0), delta(0, 2)])
    out = np.zeros_like(color, dtype=np.float32)
    crossed_left, crossed_top = left >= F(threshold), top >= F(threshold)
    out[..., 0] = crossed_left & (left >= F(.5)*maximum)
    out[..., 1] = crossed_top & (top >= F(.5)*maximum)
    # Actual website sets autoClear=false and SMAAPass.clear=false. The fragment
    # discard happens BEFORE local contrast adaptation, retaining previous RT.
    # A None previous_edges value means an explicitly fresh zero-filled target.
    if previous_edges is not None:
        previous_edges = np.asarray(previous_edges, dtype=np.float32)
        if previous_edges.shape != color.shape or not np.isfinite(previous_edges).all():
            raise ValueError('previous_edges must be finite and match composite HxWx4')
        discarded = ~(crossed_left | crossed_top)
        out[discarded] = previous_edges[discarded]
    return half_target(out)


def search_length(search, edges_rg, bias):
    p = np.array(edges_rg, dtype=np.float32, copy=True)
    p[..., 0] = F(bias)+p[..., 0]*F(.5)
    return F(255)*sample_nearest(search, p)[..., 0]


def search_axis(edges, search, initial, end, resolution, direction, max_steps=8):
    """Literal source loop: step happens before the continuation condition."""
    coords = np.array(initial, dtype=np.float32, copy=True)
    count = len(coords)
    e = np.zeros((count, 2), dtype=np.float32)
    active = np.ones(count, dtype=bool)
    axis = 0 if direction in ('left', 'right') else 1
    step_sign = -1 if direction in ('left', 'down') else 1
    for _ in range(max_steps):
        ids = np.flatnonzero(active)
        if not len(ids):
            break
        e[ids] = sample_linear(edges, coords[ids])[..., :2]
        coords[ids, axis] += F(step_sign*2)*resolution[axis]
        if direction == 'left':
            keep = (coords[ids, 0] > end[ids]) & (e[ids, 1] > F(.8281)) & (e[ids, 0] == 0)
        elif direction == 'right':
            keep = (coords[ids, 0] < end[ids]) & (e[ids, 1] > F(.8281)) & (e[ids, 0] == 0)
        elif direction == 'up':
            keep = (coords[ids, 1] > end[ids]) & (e[ids, 0] > F(.8281)) & (e[ids, 1] == 0)
        else:
            keep = (coords[ids, 1] < end[ids]) & (e[ids, 0] > F(.8281)) & (e[ids, 1] == 0)
        active[ids] = keep
    # Preserve separate additions from GLSL, not a reassociated 3.25 expression.
    undo_sign = -step_sign
    coords[:, axis] += F(undo_sign*.25)*resolution[axis]
    coords[:, axis] += F(undo_sign)*resolution[axis]
    coords[:, axis] += F(undo_sign*2)*resolution[axis]
    pair = e if axis == 0 else e[:, ::-1]
    bias = .5 if direction in ('right', 'down') else 0
    coords[:, axis] += F(step_sign)*resolution[axis]*search_length(search, pair, bias)
    return coords[:, axis]


def area_lookup(area, distance, e1, e2):
    # Positive round() inputs: fallback GLSL ES100 round is floor(x+.5).
    crossing = np.stack([e1, e2], axis=-1)
    rounded = np.floor(F(4)*crossing+F(.5))
    p = F(16)*rounded + distance
    inv = F(1)/np.array([160, 560], dtype=np.float32)
    p = p*inv + F(.5)*inv
    # Source subsampleIndices = ivec4(0): no vertical 1/7 subtexture shift.
    return sample_linear(area, p)[..., :2]


def weight_pass(edges, area, search, max_steps=8):
    """Vo/SMAABlendingWeightCalculationPS, source offset 366220."""
    h, w = edges.shape[:2]
    resolution = F(1)/np.array([w, h], dtype=np.float32)
    out = np.zeros_like(edges, dtype=np.float32)
    # Only pixels with a source edge execute expensive search functions.
    for channel in (1, 0):
        yy, xx = np.nonzero(edges[..., channel] > 0)
        if not len(xx):
            continue
        uv = (np.stack([xx, yy], axis=-1).astype(np.float32)+F(.5))*resolution
        pixcoord = uv/resolution
        o0xy = uv + resolution*np.array([-.25, .125], dtype=np.float32)
        o0zw = uv + resolution*np.array([1.25, .125], dtype=np.float32)
        o1xy = uv + resolution*np.array([-.125, .25], dtype=np.float32)
        o1zw = uv + resolution*np.array([-.125, -1.25], dtype=np.float32)
        if channel == 1:
            start, finish = o0xy, o0zw
            left = search_axis(edges, search, start, start[:, 0]-F(2)*resolution[0]*F(max_steps), resolution, 'left', max_steps)
            right = search_axis(edges, search, finish, finish[:, 0]+F(2)*resolution[0]*F(max_steps), resolution, 'right', max_steps)
            coords = np.stack([left, o1xy[:, 1]], axis=-1)
            e1 = sample_linear(edges, coords)[:, 0]
            coords[:, 0] = right
            distance = np.stack([left, right], axis=-1)/resolution[0]-pixcoord[:, 0:1]
            coords[:, 1] -= resolution[1]
            # EXACT SOURCE MACRO: float(ivec2(1,0)) == 1, broadcast to both axes.
            e2 = sample_linear(edges, coords + resolution)[:, 0]
            out[yy, xx, :2] = area_lookup(area, np.sqrt(np.abs(distance)), e1, e2)
        else:
            start, finish = o1xy, o1zw
            up = search_axis(edges, search, start, start[:, 1]-F(2)*resolution[1]*F(max_steps), resolution, 'up', max_steps)
            down = search_axis(edges, search, finish, finish[:, 1]+F(2)*resolution[1]*F(max_steps), resolution, 'down', max_steps)
            coords = np.stack([o0xy[:, 0], up], axis=-1)
            e1 = sample_linear(edges, coords)[:, 1]
            coords[:, 1] = down
            distance = np.stack([up, down], axis=-1)/resolution[1]-pixcoord[:, 1:2]
            coords[:, 1] -= resolution[1]
            # EXACT SOURCE MACRO: float(ivec2(0,1)) == 0, so no offset here.
            e2 = sample_linear(edges, coords)[:, 1]
            out[yy, xx, 2:] = area_lookup(area, np.sqrt(np.abs(distance)), e1, e2)
    return half_target(out)


def neighborhood_pass(color, weights):
    """Ho/SMAANeighborhoodBlendingPS, source offset 374470. No OETF afterward."""
    a = np.empty_like(weights)
    a[..., 0] = weights[..., 0]
    a[..., 2] = weights[..., 2]
    a[..., 1] = neighbor(weights, 0, -1)[..., 1]
    a[..., 3] = neighbor(weights, 1, 0)[..., 3]
    ox = np.where(a[..., 3] > a[..., 2], a[..., 3], -a[..., 2])
    oy = np.where(a[..., 1] > a[..., 0], -a[..., 1], a[..., 0])
    horizontal = np.abs(ox) > np.abs(oy)
    ox, oy = np.where(horizontal, ox, F(0)), np.where(horizontal, F(0), oy)
    strength = np.maximum(np.abs(ox), np.abs(oy))[..., None]
    yy, xx = np.indices(color.shape[:2])
    px = np.clip(xx+np.sign(ox).astype(int), 0, color.shape[1]-1)
    py = np.clip(yy+np.sign(oy).astype(int), 0, color.shape[0]-1)
    opposite = color[py, px]
    base = np.array(color, dtype=np.float32, copy=True)
    opposite = np.array(opposite, dtype=np.float32, copy=True)
    base[..., :3] = np.power(base[..., :3], F(2.2))
    opposite[..., :3] = np.power(opposite[..., :3], F(2.2))
    mixed = base*(F(1)-strength)+opposite*strength
    mixed[..., :3] = np.power(mixed[..., :3], F(1)/F(2.2))
    return np.where((np.sum(a, axis=-1) < F(1e-5))[..., None], color, mixed).astype(np.float32)


def process(rgba, area_path, search_path, previous_edges=None):
    """Return top-down stages. Composite must already be RGBA8-valued.

    previous_edges: top-down float32 edge stage from preceding SAME-SIZE frame.
    None explicitly assumes a new zero-filled edge RT. For website no-clear
    history semantics, feed stages['edges'] into the next call. Unknown browser
    prehistory cannot be reconstructed from a single color frame.
    """
    color = np.asarray(rgba, dtype=np.float32)
    if color.ndim != 3 or color.shape[-1] != 4 or min(color.shape[:2]) < 1:
        raise ValueError('Expected nonempty HxWx4 RGBA input')
    if not np.isfinite(color).all() or np.min(color) < 0 or np.max(color) > 1:
        raise ValueError('Expected finite, display-encoded RGBA values in [0,1]')
    if np.max(np.abs(color*F(255)-np.rint(color*F(255)))) > 1e-3:
        raise ValueError('Input is not an RGBA8 composite. Quantize explicitly before SMAA.')
    area, search = load_tables(area_path, search_path)
    color = np.ascontiguousarray(color[::-1])
    previous = None if previous_edges is None else np.ascontiguousarray(previous_edges[::-1])
    edges = edge_pass(color, previous_edges=previous)
    weights = weight_pass(edges, area, search)
    neighborhood = neighborhood_pass(color, weights)
    return dict(composite=color[::-1], edges=edges[::-1], weights=weights[::-1],
                neighborhood=neighborhood[::-1], output=unorm8_target(neighborhood)[::-1])


def write_stages(stages, output_folder):
    target = Path(output_folder)
    target.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target/'stages.npz', **stages)
    for name, value in stages.items():
        raw = np.floor(np.clip(value, 0, 1)*255+.5).astype(np.uint8)
        Image.fromarray(raw, 'RGBA').save(target/f'{name}-rgba.png')
        # RGB diagnostic avoids zero-alpha edge data disappearing in image viewers.
        if name in ('edges', 'weights'):
            Image.fromarray(raw[..., :3], 'RGB').save(target/f'{name}-rgb-diagnostic.png')
    # Alpha of weights is data: save a separate diagnostic, never replace stage alpha.
    Image.fromarray(np.floor(np.clip(stages['weights'][..., 3], 0, 1)*255+.5).astype(np.uint8), 'L').save(target/'weights-a-diagnostic.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='RGBA8 PNG or float32 .npy, already display encoded and premultiplied')
    parser.add_argument('--area', required=True, type=Path)
    parser.add_argument('--search', required=True, type=Path)
    parser.add_argument('--previous-edges', type=Path, help='Previous top-down edge .npy, or stages.npz with edges key; omitted means fresh zero-filled target')
    parser.add_argument('--output-folder', required=True, type=Path)
    args = parser.parse_args()
    if args.output_folder.exists() and any(args.output_folder.iterdir()):
        parser.error('Output folder must be absent or empty, preserving existing comparison results')
    rgba = np.load(args.input) if args.input.suffix.lower() == '.npy' else np.asarray(Image.open(args.input).convert('RGBA'), dtype=np.float32)/F(255)
    started = time.perf_counter()
    previous = None
    if args.previous_edges:
        loaded = np.load(args.previous_edges)
        previous = loaded['edges'] if isinstance(loaded, np.lib.npyio.NpzFile) else loaded
    result = process(rgba, args.area, args.search, previous_edges=previous)
    write_stages(result, args.output_folder)
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    report = dict(source_sha256=SOURCE_SHA256, script_sha256=digest(__file__), input_sha256=digest(args.input),
                  area_sha256=digest(args.area), search_sha256=digest(args.search), width=rgba.shape[1], height=rgba.shape[0],
                  seconds=time.perf_counter()-started, edge_pixels=int(np.count_nonzero(np.any(result['edges'][..., :2], axis=-1))),
                  changed_pixels=int(np.count_nonzero(np.any(result['output'] != result['composite'], axis=-1))),
                  status='prototype: source-translated CPU, full-resolution GPU comparison outstanding',
                  edge_history='previous edge RT supplied' if previous is not None else 'fresh zero-filled target assumption',
                  previous_edges_sha256=digest(args.previous_edges) if args.previous_edges else None,
                  array_contract='top-down float32; input/display-encoded premultiplied RGBA8; edge and weights quantized to float16; final RGBA8',
                  limitations=['Float32 raster interpolation / texture filtering / rounding may differ from WebGL', 'GPU equivalence not established', 'Actual website does not clear edge RT; browser prehistory must be known for exact frame comparison'])
    (args.output_folder/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
