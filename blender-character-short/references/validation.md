# Validation and limits

## Current distribution: v07

This repository distributes the v07 portable skill. The independent two-character whole-package technical reuse result belongs to v05; the final production videos were made with v06. v07 has packaging, syntax and CLI evidence, but has not completed its own independent whole-package production rerun. The original evidence project and media are not distributed here.


The skill is a tested production candidate, **not an accepted strict reproduction or reference-quality filmmaker**. Rendering, performance and independent reuse are separate gates. Evidence projects are `outputs/skill-iteration-20261027` and `outputs/skill-iteration-20261029`; their run manifests, exact commands, hashes and visual-review records are authoritative for each frozen version.

Use [S] for source code, [G] for observed website runtime/GPU, [B] for Blender execution/output, and [A] for inference/adaptation. Static GLB/manifest inspection is asset evidence, not [G]. CPU formula tests are labeled CPU and do not become Blender or website GPU tests.

## Historical verified scope (Oct27; later results below)

| Capability | Actual execution | Boundary |
|---|---|---|
| Environment/import | Blender4.5.15 LTS / Eevee; mmd_tools4.5.14; two authorized PMX characters, original rigs, packed textures and existing morphs | No MMR-generated controls, physics, walking or general retargeting claim |
| New production | Two10-second paper-plane stories, two camera arrangements each, editable scenes and complete240-frame source-post candidates | Four boards were diagnostic; candidate render remains approximate in the listed unsupported branches |
| Action/camera improvement | Same-frame v03/v04 comparison found clearer Q plane/hair separation and larger late framing, and earlier Ni landing close-up | Q plane exits upper edge at8s as an explicit creative tradeoff; only sampled visual verification |
| Fresh PMX reuse | An independent review session, initially no parent history, supplied skill + assets/config + new star story; both192-frame/8-second/24fps/640×360 outputs completed | v1 technical path passed, but story placement failed. v2 is a disclosed feedback-informed retry, not a second untouched context |
| Landmark correction | Frozen v03-landmarks rebuilt both from PMX; all28 frozen file hashes matched; actual shoulders/arm lengths used; no hand reach clamps remained | Q v2 shoulder height improved but depth remained ambiguous and hair top cropped; Ni final face improved but initial star overlapped clothing. Technical completion is not story fidelity |
| Rendering formulas | Eleven actual32×32 Eevee cases: shadow boundaries/gates, Face alpha/mirror, specular, rim, SkinRamp and Matcap | Max ROI error .00048828125, tolerance .001; fixed Normal/View and explicit texture tolerance exclude geometric/TBN/runtime equivalence |
| Static source probes | Dorm v03 outline branch corrected and rendered; Ni v03 Face smoothing corrected and rendered; raw/AOV and post stages preserved | Dorm static GLB outline is not an animated PMX outline; small Ni neutral-pose difference is not an overall aesthetic improvement |
| Source post | Both characters executed raw+AOV → box/Bloom/curve/LUT → PNG → H.264 → full decode; CPU known-input algebra/alpha/non-HDR/oversized tests passed | Ni profile is diagnostic until its own runtime parameters are confirmed; source MRT coverage is not fully reproduced |
| SMAA module | Source-derived three-pass CPU implementation;37 CPU +4 independent checks; two actual192-frame sequences encoded/decoded | GPU numerical parity pending; sparse captured bytes cannot replace full-size composite/floating stages/history |
| Recovery | Q raw budget pause and corrupt frame2 recovery: frame1 hash preserved, regenerated rgba/weight identical. SMAA CPU terminated atframe24, damaged/missing edge and alteredPNG recovered, all192frames/state identical | Raw corruption was injected on Q only; do not claim both characters had that same fault injection |
| Encoding identity | Actual four-frame encoding and12 guards bind ordered PNG hashes, encoder settings and video bytes; stale outputs rejected without replacement | Full updated run_short entrypoint requires its own frozen from-PMX run; helper tests are not that run |
| Eye controls | Both existing binocular controls rendered in matched disabled/enabled tests; Q15° target aid, adult8° restrained variant examined | Per-character existing constraints only; no arbitrary-eye-rig or accurate line-of-sight guarantee. Full newly baked sequence review remains separate |

## 2026-10-29 additions (frozen scope before independent rerun)

- Both latest acting-v3 scenes reopened with zero missing in-use images, rendered
  actual representatives, and produced complete new192-frame/24fps/8-second
  source-post+SMAA videos. This recovers a prior unfinished production step;
  it is not another fresh-PMX reuse test.
- Source GLB outline: both roles baked48 changing head/camera/lens frames,
  reopened and checked all coordinates; 10 geometry/negative tests and20
  actual Eevee color/discard/Bloom fixtures. Four on/off48-frame diagnostics
  decoded; sampled1/24/48 comparisons support the stated outline behavior.
  See [outline](outline.md) for exact tolerance and unsupported cases.
- Four new8-second A/B contact animatics completed at480x270/8samples and were
  decoded. Contact-point baking ran on both original PMX rigs, with50 full-
  contact frames per character. Initial bone-center anchors penetrated thick
  gloves despite gap=0. Deformed-surface calibration ran at80/100/124 on both;
  revised anchors reduced the deep intersection in matched close views.
  Full corrected source-post sequences and independent use remain separate.
- Story-owned poses rebuilt both characters without a `performance` table in
  character JSON; actual pose/feet/prop/contact/shapes/shots reports matched
  legacy placement exactly. This verifies input separation, not a new story.
- The standalone gaze CLI now ran on both characters at80/124. It removes only
  the tested control's existing curves, explicitly selects diagnostic cameras,
  and asserts the intended control/camera survived render evaluation. Matched
  frame80 images show iris movement without obvious white-of-eye overrun at
  the supplied limits. This does not establish accurate line-of-sight tracking.
- A first contact close-up attempt was invalid: timeline camera markers
  replaced the requested diagnostic camera. Its outputs are retained as failed
  inspection evidence. Clearing markers only in isolated working copies and
  asserting actual camera identity produced the valid matched closeups. A
  successful render call alone did not pass that visual check.

The v05 whole-package independent run subsequently completed as recorded below.
Strict rendering and performance remain unpassed.


## Completed Oct29 v05 independent run and v06 extensions

An independent review session began without parent
history, supplied only frozen v05, raw assets/character mappings, runtime paths
and a new paper-plane brief. It authored two camera arrangements per role,
reviewed and revised its own inputs, and ran the entire entrypoint from PMX.
No historical scene/video/log, extra oral technical solution or frozen-code
hotfix was needed. Q216frames/9seconds and Ni228frames/9.5seconds completed at
24fps,640x360, silent source post+SMAA. All66 commands returned0; both final
scenes reopened with no missing in-use images and rendered representatives.
All152 supplied input hashes and39 frozen source/doc hashes matched. Generated
bytecode was disclosed separately and excluded from version archives.

The input list, context ID, method audit, exact commands, stories/configs,
output hashes and sampled observations are archived under project
`independent-reuse-v05/execution-context`. No reach clamp, foot drift or
quaternion sign discontinuity was detected. This establishes **v05 technical
reuse**, not continuous viewing, full collision proof or strict reproduction.
A newer freeze requires its own result; consult the project acceptance matrix.

The v06 source-GLB morph extension is detailed in [outline](outline.md). It has
seven CPU accessor and seven Blender formula/guard cases, a24-frame Nietiya
on/off sequence, actual stale-morph rejection and both old48-frame regressions.
Only named relative POSITION-only targets are supported; Q active morphs remain
untested. An independent read-only reviewer found NaN could evade error
thresholds. Finite checks were added and tested with actual in-memory Blender
corruptions, without changing saved scenes. The first negative test expected
an infinity-specific error, but Blender clamped the value and basis matching
correctly rejected it; that failed assertion is retained, not erased.

Both characters also rebuilt/rendered optional panels and area-light sets.
Default Bloom weight matched exactly; raw radiance was nearly, not bitwise,
identical (Q max.00048828125, Ni max.0000457763671875; mean below1.4e-9).
At frame80, removing panels improved Q's close-shot isolation; alternate warm
lighting had no clear character-detail benefit. Nietiya's frame showed no useful
panel difference. This is a creative-stage test, not source lighting acceptance.

A prop-footprint audit exposed remaining star-tip overlap after single-ray
calibration. Separate corrected scenes were tested across50 full-contact
frames per role: minimum sampled directional clearance Q.0006922H,
Ni.0009938H. Fixed-camera front80/upper124 comparisons showed reduced corner
intersection. Q up to19 misses and Ni42 misses/1 grazing hit remain unverified;
this is not a whole-mesh collision or subframe pass. No automatic correction
is claimed. A prior single-ray suggestion must not overwrite a justified
footprint adjustment without rechecking the new pose/prop and visible contact.

## Overall gates

**Strict rendering:** source-matched asset/pose/camera/runtime/background/RT conditions are incomplete. Ni environment cubemaps, HairHET/eye stencil, transparent depth/XT/MRT, shadow maps, effects, TBN equivalence, PMX dynamic outlines and unsupported morph semantics are unresolved; the limited source-GLB relative POSITION-only case now has its own evidence. The new GLB cache closes a narrower skin/camera case. Source SMAA CPU success is not GPU parity. A known critical approximation cannot be promoted by a better-looking image.

**Performance:** three public Bilibili works were actually sampled through the user's Chrome; their links and timepoints are in the evidence project's reference report. They establish limited Q/chibi reference observations, not an adult-Ni-specific standard. Local video assessment is full-file decode plus sampled frames, not continuous normal-speed viewing. Fine timing, motion/flicker continuity and sound remain unaccepted. All current automatic outputs are silent; no audio listening was performed.

**Reuse:** the core fresh-PMX technical path is verified on two characters; the independent execution record distinguishes initial clean-context work from feedback retries. The v05 whole-package technical run passed as described below. A later freeze still needs its own record; project acceptance matrices track subsequent results. Do not infer a whole-package pass from a subset of matching script hashes or from a freshly named directory.

The historical two-character best scenes/videos and skill are preserved with hashes and rollback archive. They used Fog Glow/material approximations and are workflow baselines, not strict-render evidence.

## Access and review limits

The required cube index returned HTTP403; a browser bundle attempt produced no files. That path was stopped. Browser opening of local video with `file:` was explicitly denied; no localhost proxy or alternate browser surface was used to bypass it. These unresolved actions are not completed work. Later routine local reads/writes and background Blender are available, but do not remove those separate restrictions.

## Updating this record

The later execution-lock addition has nine actual Windows-process checks:
concurrent refusal with no child side effect, release/reacquire, exit-code
propagation, unavailable executable recovery, and injected post-spawn metadata
failure/interrupted waiting while another process still receives75. Unicode
and spaces in the lock path were exercised. A read-only reviewer identified
the post-spawn release bug before correction; both the original tests and
corrected fault-injection evidence are retained in the project. This does not
establish arbitrary-host process discovery, forced-wrapper-death cleanup, or
an independent whole-package filmmaking pass for the new freeze. Video producer
versions remain separately pinned; do not resume their folders with new hashes.

For a new pass record inputs, frozen script/config hashes, exact frame range, output/command paths, observed visual/audio scope and remaining limitations. Reopen final delivered scenes, verify packed/missing resources and render a real representative frame; also inspect the external-post output. Structure validation proves packaging only. Announce overall success only with actual evidence for all three gates.

Keep models, textures, lookup images, dependency binaries and character-specific bone/material maps outside the skill. The detailed project logs stay in the evidence project rather than being copied into the generic procedure.
