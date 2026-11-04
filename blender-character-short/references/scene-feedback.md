# Let the scene acknowledge a real outcome

Use a restrained material response when it makes the plot easier to read: for
example, a receiving tray warms after a part is safely seated. Keep the original
material style and character palette. Review the actual shot; a light does not
repair unclear acting or invalid placement.

`run_short.py --scene-feedback-plan PLAN.json` runs after acting/gaze and before
whole-scene tempo. Omitting it keeps the prior route. Standalone use:

```text
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python scripts/bake_scene_feedback.py -- --blend SOURCE.blend --character CHARACTER.json --plan PLAN.json --output NEW.blend --report NEW.json
```

Schema1 has exactly these fields:

| Field | Content |
| --- | --- |
| `schema` | Integer1. |
| `prop`, `receiver`, `indicator` | Distinct existing visible external meshes; not the character mesh. |
| `search_frames` | Source integer start/end within a1..1200frame scene. |
| `stable_frames` | Integer2..48 consecutive qualifying source steps. First sample has no previous motion measurement. |
| `xy_margin_H` | Finite0..0.1 inner footprint margin, covering receiver bevel width. |
| `bottom_gap_H` | Ordered signed interval within[-0.005,0.02], relative to actual receiver top. |
| `max_prop_height_H` | Positive, at most0.2; bounds evaluated world height as a flatness condition. |
| `max_step_H` | Positive, at most0.1; maximum corresponding evaluated vertex displacement per source frame, including rotation. |
| `ramp_frames` | Integer1..120; enough source time must remain after confirmation. |
| `on_color` | Three finite linear RGB values in[0,1]. |
| `mix`, `emission_strength`, `bloom_weight` | Finite0..1,0..5,0..1. Start with a restrained mix/emission and inspect final post. |

The receiver is a static, horizontal, axis-aligned closed cuboid with all six
faces, optionally beveled within the margin. The prop supports fixed evaluated
topology with bevel/solidify only. Five million vertex-frames and500000protected
bone/object-frames bound the work. Floating, penetrating, briefly stopped,
rapidly rotating and moving-receiver cases are rejected before material change.

The indicator uses one unanimated opaque material, with one active surface and
no shader groups, transparency, transmission, volume or displacement. Both
direct Principled and supported mixed toon surfaces work. Its independent
object material keeps the original graph and adds a bounded emission mix;
zero signal retains original surface and Bloom-weight inputs. Other users of
the original material remain unchanged. The helper protects rig/rest/mesh/weights
and all bone/object world states. It does not reassign the character material.

This is one latched confirmation, not a live sensor: later removal does not
automatically reset it. Bbox containment, bottom gap, height and vertex step are
declared geometry conditions, not closed-volume contact, friction or subframe
stability. A tempo map changes delivered duration and sampling; inspect final
saved frames and actual output. Preserve failed conditions rather than moving
the cue time to hide invalid seating.

`verify_scene_feedback.py --output NEW.json` runs seven actual Blender synthetic
cases in a new factory background process. It refuses a UI or loaded project.
These tests cover mixed surface support, material isolation and invalid seating;
they do not establish character acting, final color or continuous viewing.
