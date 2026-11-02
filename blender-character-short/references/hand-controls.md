# Hand controls and contact

Inventory the actual weighted rig before writing finger acting. A familiar finger
name or a long bone chain does not establish separately deforming fingers. Some
chibi gloves have one thumb group and one mitten group even when the skeleton
contains many unweighted finger descendants.

```text
blender --background --factory-startup --python-exit-code 1 \
  --python scripts/inspect_hand_controls.py -- \
  --blend BASELINE.blend --character CHARACTER.json --output HAND_INVENTORY.json
```

The character input supplies existing `bones.left_wrist` and `bones.right_wrist`.
The read-only report lists original descendant hierarchy, rest matrices, pose
constraints and assignments whose weights exceed `.01` (configurable with
`--min-weight`). It hashes the scene before/after and never saves it. Counts use
original mesh assignments, not evaluated pose response. Indirect or constrained
controls need inspection even when their own group has no counted vertices.

Keep any selected joint names in the external character `bones` map and its
local XYZ degree rotations in existing story `poses[].rotations`. Do not add
Nanami names, fixed hand geometry or a role-specific grasp table to generic code.
The builder converts these local Euler rotations to keyed quaternions. Derive
the intended bend in the inspected rest frame and confirm actual deformation in
matched views; copying a wrist/world axis into a finger's local Euler axis can
rotate the glove in the wrong direction.

Compare open, moderate and stronger static poses before animating. Preserve the
original deform bones and weights. Check the actual handle, shaft and nearby
guide surfaces, then test contact entry, the complete held range and release.
Recheck calibrated directional palm footprints after changing a glove pose.
A nonnegative directional gap and zero sampled triangle intersections do not
prove volume clearance, physical grip or convincing acting. Increasing clearance
can make a hand float. Keep the failed pose and diagnostic evidence when rejecting it.

For a controlled test, compare all other bone world transforms and every bone's
local translation/scale against the same source performance. A changed thumb's
unweighted children legitimately inherit its world rotation: record that exact
descendant set, verify its weights and compare its local rotations separately.
Do not exclude the whole hand, arm or body to obtain a passing regression.

The Nanami two-joint trial used 10 degrees at the thumb and 15 at the mitten
cluster, with existing 25 pose keys, delayed closure on arrival and reopening
after adjustment. All 480 nonfinger world transforms were unchanged; 156 held
frames had zero detected hand/handle or named-control surface intersections,
and the directional footprint passed unchanged thresholds. Three native frames
and a matched open/curl pair were actually viewed. This is a local input trial,
not a complete preview, continuous motion acceptance, universal angle preset,
five-finger grasp system or cross-character test.
