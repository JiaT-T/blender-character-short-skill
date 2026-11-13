# Smooth an animated cord with fixed endpoints

Use this route when an existing animated POLY cord shows visible corners.
Preserve the reviewed source project and supply an external numeric plan. Run
under the shared execution lock in background Blender, with the project's
required addons already enabled. Keep source projects, plans and outputs outside
the skill and repository.

## Supported input

Native evidence covers Blender4.5.15 and the legacy `Action.fcurves` interface.
Require one independent local 3D curve, one open POLY spline with4..128 controls,
unit weights, a unit-scale rigid object transform, and a unique coordinate Action.
Require plain LINEAR XYZ channels with constant extrapolation. Optional animated
W channels must stay identically one. Object animation, drivers, NLA, modifiers,
constraints and curve shape keys require a separately reviewed route.

The fitter preserves endpoint channels, weight channels and chord projections.
It adjusts only the perpendicular bow. Bound control displacement in coordinate
units; relative bow factors are unreliable near a straight cord. A source with no
bow direction cannot gain slack automatically. Nonmonotone chord projections are
outside this route. A control displacement bound is not a surface-contact proof.

## External plan

Lengths use the input coordinate unit. These example values assume metres:

```json
{
  "schema": 1,
  "object": "Cord",
  "frames": [1, 9],
  "sample_times": [1, 2, 3, 4, 4.001, 5, 6, 7, 8, 8.999, 9],
  "target_length": 0.12,
  "max_displacement": 0.0005,
  "length_tolerance": 0.000001,
  "maximum_key_step": 0.25
}
```

Include every output frame, contact boundary and required fractional probe in
`sample_times`. The tools also collect original knots and candidate knots.
Planning admits at most16000 keys; shared read-back planning admits at most one
million control-point evaluations. Exceeding either budget stops before target
curve mutation. Preserve coverage when preparing a smaller reviewed source.

## Author and independently reopen

Use the reviewed project launcher to run `scripts/smooth_curve.py` inside Blender
with these arguments:

```text
--source <original.blend> --source-sha256 <sha256> --plan <plan.json> --output <new-candidate.blend> --report <new-author-report.json>
```

Run `scripts/verify_smoothed_curve.py` in a distinct background Blender process:

```text
--source <original.blend> --source-sha256 <original-sha256> --candidate <new-candidate.blend> --candidate-sha256 <candidate-sha256> --plan <same-plan.json> --report <new-readback-report.json>
```

The independent reader checks actual serialized channels at original/candidate
knots, required times and interval quarter/mid/three-quarter probes. Original
knots remain required even when a damaged candidate omits a short source peak.
It checks native curve length against independent cubic integration, requires
two matching native measurement resolutions, and verifies endpoints, weights,
world transform, displacement and unchanged input bytes. Higher `calc_length`
resolution alone does not establish greater accuracy.

Treat author key counts as proposals; use the fresh reader for saved counts and
actual measured bounds. Retain partial outputs and reports on failure. Inspect
the existing outcome before retrying. Bind new render output to the new project
hash and producer identity.

## Portable native regression

Run `scripts/curve_native_fixture.py` twice, each time in a new factory background
Blender process under the shared lock. Pass the same reviewed module directory
and a dedicated output directory outside the repository:

```text
--module-dir <scripts-directory> --output-root <new-fixture-directory> --stage author
--module-dir <same-scripts-directory> --output-root <same-fixture-directory> --stage verify
```

The first stage constructs an asset-free moving cord and invokes the real writer;
the second checks a different process, code/input hashes and the real reader.
Review contacts, intersections, the full encoded movie and normal-speed playback
separately. Sampled curve checks do not certify dynamics or every real time.
