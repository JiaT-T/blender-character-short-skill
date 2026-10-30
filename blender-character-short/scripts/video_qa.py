#!/usr/bin/env python3
"""Decode a video completely, report timing, and create a labeled sample sheet.

Requires imageio-ffmpeg and Pillow. This is a file/parameter check and a sampled
visual aid, not evidence that a person or model watched continuous playback.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


def parse_showinfo(log: str) -> tuple[list[dict], Fraction | None]:
    frames = []
    rate = None
    for line in log.splitlines():
        if 'showinfo' not in line:
            continue
        m = re.search(r'config in time_base:.*frame_rate:\s*(\d+/\d+)', line)
        if m:
            candidate = Fraction(m.group(1))
            if candidate:
                rate = candidate
        m = re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([-+\d.eE]+)', line)
        size = re.search(r'\bs:(\d+)x(\d+)\b', line)
        if not m or not size:
            continue
        duration = re.search(r'\bduration_time:\s*([-+\d.eE]+)', line)
        frames.append({
            'index': int(m.group(1)),
            'pts': int(m.group(2)),
            'pts_seconds': float(m.group(3)),
            'duration_seconds': float(duration.group(1)) if duration else None,
            'width': int(size.group(1)), 'height': int(size.group(2)),
        })
    return frames, rate


def get_font(size: int):
    try:
        return ImageFont.truetype('DejaVuSans.ttf', size)
    except OSError:
        return ImageFont.load_default(size=size)


def contact_sheet(ffmpeg: str, video: Path, out: Path, frames: list[dict], count: int, columns: int, width: int) -> tuple[Path, list[dict]]:
    total = len(frames)
    indices = sorted({round(i * (total - 1) / (min(count, total) - 1)) for i in range(min(count, total))}) if total > 1 and count > 1 else [0]
    samples_dir = out / 'samples'
    samples_dir.mkdir(exist_ok=True)
    selection = '+'.join(f'eq(n\\,{i})' for i in indices)
    command = [ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-i', str(video),
               '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', f'select={selection},scale={width}:-2',
               '-fps_mode', 'vfr', '-start_number', '0', str(samples_dir / 'sample_%03d.png')]
    proc = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if proc.returncode:
        raise RuntimeError(f'Contact-sheet extraction failed: {proc.stderr}')
    paths = [samples_dir / f'sample_{i:03d}.png' for i in range(len(indices))]
    images = [Image.open(p).convert('RGB') for p in paths]
    if not images:
        raise RuntimeError('No visual samples extracted')
    cell_w, image_h = images[0].size
    label_h, pad, title_h = 44, 12, 74
    cell_h = image_h + label_h
    cols = min(columns, len(images))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new('RGB', (cols * cell_w + (cols + 1) * pad, title_h + rows * cell_h + (rows + 1) * pad), '#161a21')
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 12), video.name, fill='white', font=get_font(21))
    draw.text((pad, 42), 'SAMPLED FRAMES - NOT CONTINUOUS PLAYBACK REVIEW', fill='#b5bbc9', font=get_font(14))
    samples = []
    for pos, (idx, img, path) in enumerate(zip(indices, images, paths)):
        x = pad + (pos % cols) * (cell_w + pad)
        y = title_h + pad + (pos // cols) * (cell_h + pad)
        sheet.paste(img, (x, y))
        ts = frames[idx]['pts_seconds'] - frames[0]['pts_seconds']
        draw.text((x + 7, y + image_h + 8), f'frame {idx + 1} / {total}    {ts:.3f}s', fill='#e2e7f0', font=get_font(16))
        samples.append({'frame_1based': idx + 1, 'time_seconds': round(ts, 6), 'image': str(path)})
    target = out / 'contact-sheet.jpg'
    sheet.save(target, quality=93)
    for img in images:
        img.close()
    return target, samples


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video', type=Path)
    ap.add_argument('--output-dir', type=Path, help='Default: VIDEO_STEM-qa beside the input')
    ap.add_argument('--expected-fps', type=float, default=24.0)
    ap.add_argument('--expected-frames', type=int)
    ap.add_argument('--expected-duration', type=float)
    ap.add_argument('--duration-tolerance', type=float, default=0.05)
    ap.add_argument('--samples', type=int, default=12)
    ap.add_argument('--columns', type=int, default=3)
    ap.add_argument('--thumbnail-width', type=int, default=480)
    ap.add_argument('--ffmpeg', help='Optional executable override')
    args = ap.parse_args()
    if args.samples < 1 or args.columns < 1 or args.thumbnail_width < 64:
        ap.error('samples/columns must be positive and thumbnail-width >= 64')
    video = args.video.resolve(strict=True)
    out = (args.output_dir or video.with_name(video.stem + '-qa')).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ffmpeg = args.ffmpeg or imageio_ffmpeg.get_ffmpeg_exe()
    version = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.splitlines()[0]
    command = [ffmpeg, '-hide_banner', '-nostdin', '-nostats', '-loglevel', 'info', '-xerror', '-err_detect', 'explode',
               '-i', str(video), '-map', '0:v:0', '-map', '0:a?', '-sn', '-dn', '-vf', 'showinfo',
               '-fps_mode', 'passthrough', '-f', 'null', '-']
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    log_path = out / 'full-decode.log'
    log_path.write_text(result.stderr, encoding='utf-8')
    frames, fps = parse_showinfo(result.stderr)
    intervals = [b['pts_seconds'] - a['pts_seconds'] for a, b in zip(frames, frames[1:])]
    duration = None
    if frames:
        last_duration = frames[-1]['duration_seconds']
        if not last_duration or last_duration <= 0:
            last_duration = float(1 / fps) if fps else (intervals[-1] if intervals else 0)
        duration = frames[-1]['pts_seconds'] - frames[0]['pts_seconds'] + last_duration
    expected_interval = 1.0 / args.expected_fps
    # showinfo decimal timestamps have limited precision; tolerate 0.1ms.
    cfr_pass = bool(frames) and all(abs(v - expected_interval) <= 0.0001 for v in intervals)
    checks = {
        'full_decode_success': result.returncode == 0 and bool(frames),
        'reported_fps_matches': fps is not None and abs(float(fps) - args.expected_fps) < 0.000001,
        'decoded_timestamps_match_expected_cfr': cfr_pass,
        'all_frame_dimensions_consistent': len({(f['width'], f['height']) for f in frames}) == 1,
    }
    if args.expected_frames is not None:
        checks['expected_frame_count_matches'] = len(frames) == args.expected_frames
    if args.expected_duration is not None:
        checks['expected_duration_matches'] = duration is not None and abs(duration - args.expected_duration) <= args.duration_tolerance
    report = {
        'video': str(video), 'file_bytes': video.stat().st_size,
        'ffmpeg': ffmpeg, 'ffmpeg_version': version,
        'decode_command': command, 'decode_exit_code': result.returncode,
        'decoded_frame_count': len(frames),
        'reported_fps': str(fps) if fps is not None else None,
        'expected_fps': args.expected_fps,
        'width': frames[0]['width'] if frames else None,
        'height': frames[0]['height'] if frames else None,
        'duration_from_decoded_pts_seconds': duration,
        'min_frame_interval_seconds': min(intervals) if intervals else None,
        'max_frame_interval_seconds': max(intervals) if intervals else None,
        'checks': checks, 'parameter_checks_pass': all(checks.values()),
        'log': str(log_path),
        'review_scope': {
            'full_file_video_and_audio_decode': result.returncode == 0,
            'parameters_checked': True,
            'contact_sheet_generated': False,
            'visual_samples_reviewed': False,
            'continuous_playback_watched': False,
            'audio_listened': False,
            'limitations': 'Decoding and samples do not establish motion continuity, lack of subtle flicker, or audio quality. Review samples and continuous playback separately.',
        },
    }
    if frames:
        try:
            sheet, samples = contact_sheet(ffmpeg, video, out, frames, args.samples, args.columns, args.thumbnail_width)
            report['contact_sheet'] = str(sheet)
            report['samples'] = samples
            report['review_scope']['contact_sheet_generated'] = True
        except Exception as exc:
            report['contact_sheet_error'] = str(exc)
    report_path = out / 'qa.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'report': str(report_path), 'passed': report['parameter_checks_pass'], 'frames': len(frames), 'fps': report['reported_fps'], 'duration': duration, 'size': [report['width'], report['height']], 'contact_sheet': report.get('contact_sheet')}, ensure_ascii=False))
    return 0 if report['parameter_checks_pass'] and report['review_scope']['contact_sheet_generated'] else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
