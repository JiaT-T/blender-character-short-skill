# Story-purpose framing

Declare the geometry needed to read each beat before adopting its camera. An
approach/stop usually needs head and feet; a relief gesture needs the hands as
well as the face. A perfectly decoded video can still crop that information.

Keep a separate external framing plan on the original source-story timeline:

```json
{
  "schema": 1,
  "ranges": [
    {"start":1,"end":60,"features":["head","left_foot","right_foot","prop"],"margin":0.02},
    {"start":61,"end":120,"features":["head","left_hand","right_hand","prop"],"margin":0.03}
  ]
}
```

Ranges must be ordered, nonoverlapping integer source frames inside the story.
Provide1..64ranges, unique known features, and finite margin0..0.25. The margin
is a fraction of each image dimension. Unrequested output frames are reported;
they do not imply complete-film coverage.

| Feature | Evaluated geometry |
| --- | --- |
| `head` | Original configured head and descendant weighted vertices, including mapped hair. |
| `left_hand`, `right_hand` | Corresponding configured wrist descendants. |
| `left_foot`, `right_foot` | The body plan's actual shoe deform root descendants. |
| `prop` | Actual `Story prop` mesh with evaluated modifiers; child component bounds are not included. |

The character plan's explicit weight threshold selects features. Original vertex
topology must be stable for weighted features. The included checker uses actual
deformed vertices and current orthographic camera bounds, including aspect and
camera shift. It does not rely on a fixed pose, guessed portrait crop or camera
name. If whole-scene tempo was used, its bound source-time map selects each
output frame's requirement.

Pass `--framing-plan PLAN.json` to `audit_body_approach.py`. Read
`framing_checked_output_frames`, `framing_unrequested_output_frames`, failures,
and `all_requested_framing_features_inside_margin`. The report binds the framing
plan and auditor dependencies separately from the actual production code.

This is an in-frame geometry test. It does not prove alpha-aware visibility,
occlusion-free hands or props, readable irises, recognizable silhouettes or
normal-speed editing. Compare matched rendered probes and the complete preview.
Use the full hair/hand envelope during a gesture, not just its most open pose.
Save camera edits as a new story/output version and rerender so the preview,
saved scene and reports stay paired.

## Verify the camera that actually rendered

Story shots use `location`, `target` and `scale`; a field named `camera` is not
a position alias. Inspect the actual saved camera/shot report, not just the
intended values in an annotation. Keep a failed configuration as a labeled
control and rebuild in a fresh directory when correcting input identity.

Blender camera timeline bindings can restore the original shot during render
evaluation, overriding a temporary `scene.camera` assignment. For matched
in-memory camera probes, temporarily remove camera bindings, select the test
camera and verify its identity after each render. Restore bindings between
original-shot controls. Preserve the source bytes and never save this temporary
unbinding over the production scene. Pre-render feature bounds alone do not
prove that a particular camera produced the image.

When the plot prop merges with the face or sleeve silhouette, compare actual
side-camera images at the action high point. Keep an approach master for feet
and path; use a separate purposeful miss/contact shot when its angle improves
the visible causal relationship. A close-up that merely enlarges an ambiguous
overlap does not solve readability. Check the entire new shot's geometry and
real rendered motion before adoption.
