# Shot planning and plan-aware movie review

These host-only tools add a shared shot table and optional review cues. They do not change a Blender scene, retime footage, judge acting, replace normal-speed viewing or approve a film. Run on a separate package/output location when a current production has a frozen producer identity. Merely adding scripts to that package changes its identity.

## Shot table

`python -B scripts/shot_plan.py --plan SHOTS.json --report NEW_CONTRACT.json`

Use schema 1, the actual saved `fps` and `fps_base`, inclusive `start`/`end`, and ordered `shots`. Optional top-level `assets` maps stable asset IDs to descriptions or local path strings. Optional shot `asset_ids` must reference unique known IDs. This validates references, not the binary assets or their existence.

Every shot declares:

- Unique `id`, narrative `beat`, `camera` and `framing` strings.
- Inclusive `start` and `end`, with no gaps/overlaps across the full plan.
- `action_start` and `action_end`: concise reusable state descriptions.
- `spatial_start` / `spatial_end`: string maps, for example actor position, facing, gaze target, screen travel direction and camera side of the scene axis. These are declarations, not geometry calculations.
- `props_start` / `props_end`: string maps, for example `ribbon: left_hand` or `door: closed`. Include relevant object ownership and attachment state.
- Optional incoming `transition`: `cut` (default), `dissolve`, `fade` or `continuous`.
- Optional `continuity_exceptions`: objects containing `field: action|spatial|props` and a nonempty `reason` explaining a deliberate change across the preceding boundary.

Different end/start descriptions yield review warnings unless explicitly explained. Comparing strings cannot decide whether an action transition is plausible or whether an axis crossing is visible. Empty prop maps are valid when no props matter. Frame range is capped at 100000 and shots at 1000.

```json
{
  "schema": 1, "fps": 24, "fps_base": 1, "start": 25, "end": 48,
  "shots": [{
    "id": "greeting", "beat": "Notice the last guest", "camera": "wide", "framing": "full body",
    "start": 25, "end": 48, "action_start": "idle", "action_end": "facing_guest",
    "spatial_start": {"actor": "stage_center", "gaze": "forward"},
    "spatial_end": {"actor": "stage_center", "gaze": "guest"},
    "props_start": {}, "props_end": {}
  }]
}
```

## Movie review cues

`python -B scripts/planned_video_review.py --video MOVIE.mp4 --plan SHOTS.json --report NEW_REVIEW.json [--settings THRESHOLDS.json]`

The first decoded video frame maps to `plan.start`, not necessarily 1. A shot's incoming cut is its first frame; signed offsets are observed minus planned cut frame. Seconds are relative to the movie start using `fps/fps_base`. A first-frame FFmpeg probe reads a rational stream rate and compares it with the rational plan rate. This does not establish constant frame timestamps: keep the existing full timestamp/decode check for that, especially for VFR inputs.

The movie is streamed as a fixed 160x90 grayscale grid using one decoder thread. Only three image states are needed, with up to 100000 decoded frames and 2000 retained findings/suppression records. Source movie SHA256 is checked before/after reading. The report binds a canonical JSON plan digest; it never edits the movie. No GPU or Blender process is launched. Report files are exclusive/new-only.

Default thresholds use normalized grayscale differences:

```json
{"jump": 0.20, "flash": 0.28, "return_similarity": 0.04, "freeze": 0.001, "freeze_frames": 12, "cut_tolerance": 2}
```

- `jump`: large adjacent-frame mean difference away from an expected hard cut.
- `flash`: two strong adjacent differences with the surrounding frames similar. Expected cut neighborhoods are excluded from this heuristic.
- `freeze`: a run of sufficiently similar frames. A held pose is not automatically a fault.
- `cut`: no strong change near an expected cut, or the nearest candidate is offset. Similar views may hide a real cut; motion can create a false candidate.
- Frame-count and reported-rate mismatch are separate review cues.

Every cue is for human review. No findings **does not mean** visual quality passed. Small details, cloth/hair shimmer, foot sliding, framing quality, sound and meaningful performance are outside these low-resolution statistics.

For intentional holds, flashes or transitions, add `review_exemptions` to the plan:

```json
{"kind": "freeze", "start": 25, "end": 48, "reason": "Deliberate still ending"}
```

Each exemption is an object in that list, with `kind: flash|jump|freeze|cut`, inclusive in-range frame interval and reason. A cue is suppressed only if its complete interval is covered; the report retains the reason and frames in `suppressed_findings`. Declaring a dissolve removes the expectation of a hard cut but does not automatically exempt flashes/motion around it: declare the intended transition interval if needed. Do not enlarge exemptions simply to remove inconvenient findings.

## Evidence boundary

Tests cover invalid/gapped shot ranges, continuity declarations, explicit exceptions, expected and offset cuts, deliberate flash/freeze inputs, non-1 frame offsets, fractional time mapping, invalid thresholds, and a tiny generated silent video decoded through the actual host FFmpeg path. This is synthetic host evidence, not a review of the running film or validation of Blender lighting/animation.
