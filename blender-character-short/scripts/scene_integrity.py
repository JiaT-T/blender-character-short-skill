"""Strict Blender project guard and reversible controller probes.

This module never opens/saves a .blend, starts Blender, or repairs a rig.
Run inside the already-open Blender file::

    before = snapshot(bpy.context.scene)
    probe_before = probe_controls(bpy.context.scene)
    # Apply the authorized material change.
    after = snapshot(bpy.context.scene)
    integrity = compare(before, after)
    probe_after = probe_controls(bpy.context.scene, baseline=probe_before)
    write_json(report_path, {"integrity": integrity, "probes": probe_after})

Snapshots are JSON serializable; large numerical arrays use lossless zlib/base64
encoding and SHA256. ``sha256`` covers all protected content. Material slots,
polygon material assignments, shader/compositor trees, render/color settings,
active selection, and scene camera are deliberately outside the protected set.
Original object/data identities, transforms, topology, UVs, stored normals,
weights, shape keys, rigs, animation, and user properties are protected.

Only new HX_/hx_ objects, their new data, HX_/hx_ collections, new HX_/hx_
geometry node groups directly referenced by those new HX objects' NODES
modifiers, a new mesh
attribute named hx_source_color, and the new scene report properties
huaxu_post_report/render_device_policy are permitted by default. Existing entries with
those names remain protected. Callers may explicitly supply other new object
names to ``compare(allowed_new_objects=...)`` after reviewing them.

No bpy dependency is imported until a Blender-only entry point is called.
"""

from array import array
import base64
import hashlib
import json
import math
from pathlib import Path
import sys
import zlib


SCHEMA = "huaxu-project-integrity-v1"
_PREFIXES = ("HX_", "hx_")
_RNA_SKIP = {"rna_type", "id_data", "users", "use_fake_user", "is_embedded_data",
             "is_library_indirect", "is_evaluated", "original", "tag",
             "is_property_set", "is_property_readonly", "is_valid"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def write_json(path, value):
    """Write an explicit caller-selected report path; never called implicitly."""
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False), encoding="utf-8")


def _id(value):
    if value is None:
        return None
    return {"name": value.name, "type": value.bl_rna.identifier,
            "library": getattr(getattr(value, "library", None), "filepath", None)}


def _value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"nonfinite": repr(value)}
    if hasattr(value, "bl_rna") and hasattr(value, "name") and hasattr(value, "library"):
        return _id(value)
    if hasattr(value, "to_dict"):
        return {str(k): _value(v) for k, v in value.to_dict().items()}
    if hasattr(value, "keys"):
        return {str(k): _value(value[k]) for k in value.keys()}
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "to_list"):
        return _value(value.to_list())
    try:
        return [_value(v) for v in value]
    except TypeError as exc:
        raise TypeError("Unserializable protected value: " + type(value).__name__) from exc


def _custom(owner):
    """Preserve values and user-property UI metadata, including legacy _RNA_UI."""
    try:
        keys = owner.keys()
    except TypeError:
        # Some bpy_struct types genuinely cannot own ID properties.
        return {"values": {}, "ui": {}}
    result = {str(k): _value(owner[k]) for k in keys}
    metadata = {}
    if hasattr(owner, "id_properties_ui"):
        for key in result:
            try:
                ui = owner.id_properties_ui(key).as_dict()
            except (TypeError, KeyError, RuntimeError):
                continue  # ID pointer/group properties do not support UI metadata.
            if ui:
                metadata[key] = _value(ui)
    return {"values": result, "ui": metadata}


def _rna(owner, skip=(), depth=0):
    """Serialize RNA settings without addresses or transient evaluation flags.

    Collections are retained in order; pointers to ID blocks use stable names.
    Editable settings and readonly collections are included. Readonly scalar
    cache/derived values are omitted except stable type/name discriminators.
    """
    if owner is None:
        return None
    result = {"rna_type": owner.bl_rna.identifier}
    omitted = _RNA_SKIP | set(skip)
    for prop in owner.bl_rna.properties:
        name = prop.identifier
        if name in omitted:
            continue
        if prop.is_readonly and prop.type not in {"COLLECTION", "POINTER"} and name not in {"name", "type"}:
            continue
        value = getattr(owner, name)
        if prop.type == "POINTER":
            if value is None:
                result[name] = None
            elif hasattr(value, "library") and hasattr(value, "name"):
                result[name] = _id(value)
            elif hasattr(value, "name") and value.bl_rna.identifier in {
                "Bone", "EditBone", "PoseBone", "ActionGroup", "BoneCollection",
                "NlaTrack", "NlaStrip", "Node", "NodeSocket", "ShapeKey",
            }:
                # Rest-bone bbone handles and FCurve.group can point backwards
                # into the collections already serialized by their owner.
                result[name] = {"rna_reference": value.bl_rna.identifier, "name": value.name}
            elif hasattr(value, "name") and any(base.identifier in {"Node", "NodeSocket"}
                    for base in _rna_bases(value.bl_rna)):
                result[name] = {"rna_reference": value.bl_rna.identifier, "name": value.name}
            elif depth < 8:
                result[name] = _rna(value, depth=depth + 1)
            else:
                raise ValueError("RNA recursion exceeded at " + name)
        elif prop.type == "COLLECTION":
            if depth >= 8:
                raise ValueError("RNA collection recursion exceeded at " + name)
            result[name] = [_rna(item, depth=depth + 1) for item in value]
        else:
            result[name] = _value(value)
    return result


def _rna_bases(rna):
    """Walk RNA inheritance without assuming a Python class is importable."""
    while rna is not None:
        yield rna
        rna = rna.base


def _blob(values, code="d", width=1):
    data = values if isinstance(values, array) and values.typecode == code else array(code, values)
    if sys.byteorder != "little":
        data = array(code, data)
        data.byteswap()
    raw = data.tobytes()
    return {"__numeric__": True, "typecode": code, "width": width,
            "count": len(data), "sha256": hashlib.sha256(raw).hexdigest(),
            "zlib_base64": base64.b64encode(zlib.compress(raw, 6)).decode("ascii")}


def _unblob(blob):
    raw = zlib.decompress(base64.b64decode(blob["zlib_base64"]))
    if hashlib.sha256(raw).hexdigest() != blob["sha256"]:
        raise ValueError("Corrupt numerical snapshot blob")
    data = array(blob["typecode"])
    data.frombytes(raw)
    if sys.byteorder != "little":
        data.byteswap()
    if len(data) != blob["count"]:
        raise ValueError("Snapshot blob count mismatch")
    return data


def _foreach(collection, field, width=1, code="d"):
    values = array(code, [0]) * (len(collection) * width)
    if values:
        collection.foreach_get(field, values)
    return _blob(values, code, width)


def _animation(owner):
    ad = getattr(owner, "animation_data", None)
    if ad is None:
        return None
    return _rna(ad)


def _shape_keys(keys):
    if keys is None:
        return None
    blocks = {}
    for block in keys.key_blocks:
        blocks[block.name] = {
            "settings": _rna(block, skip={"data", "relative_key", "points", "normals_vertex_get", "normals_polygon_get", "normals_split_get"}),
            "relative_key": block.relative_key.name if block.relative_key else None,
            "coordinates": _foreach(block.data, "co", 3),
            "custom": _custom(block),
        }
    return {"id": _id(keys), "use_relative": keys.use_relative,
            "eval_time": keys.eval_time, "key_order": [b.name for b in keys.key_blocks],
            "blocks": blocks, "custom": _custom(keys), "animation": _animation(keys)}


def _attribute(attr):
    fields = {
        "FLOAT": ("value", 1, "d"), "INT": ("value", 1, "q"),
        "INT8": ("value", 1, "q"), "BOOLEAN": ("value", 1, "b"),
        "FLOAT_VECTOR": ("vector", 3, "d"), "FLOAT2": ("vector", 2, "d"),
        "FLOAT_COLOR": ("color", 4, "d"), "BYTE_COLOR": ("color", 4, "d"),
        "INT32_2D": ("value", 2, "q"), "QUATERNION": ("value", 4, "d"),
        "FLOAT4X4": ("value", 16, "d"),
    }
    if attr.data_type in fields:
        field, width, code = fields[attr.data_type]
        values = _foreach(attr.data, field, width, code)
    else:
        values = [_rna(item) for item in attr.data]
    return {"domain": attr.domain, "data_type": attr.data_type, "values": values}


def _mesh(mesh):
    # This evaluates the split-normal cache only; it does not set custom normals.
    if hasattr(mesh, "calc_normals_split"):
        mesh.calc_normals_split()
    if hasattr(mesh, "corner_normals"):
        normals = _foreach(mesh.corner_normals, "vector", 3)
    else:
        normals = _foreach(mesh.loops, "normal", 3)
    uv = {}
    for layer in mesh.uv_layers:
        row = {"uv": _foreach(layer.data, "uv", 2),
               "active_render": layer.active_render, "active_clone": layer.active_clone}
        for field in ("pin_uv", "select", "select_edge"):
            if layer.data and hasattr(layer.data[0], field):
                row[field] = _foreach(layer.data, field, code="b")
        uv[layer.name] = row
    # Sparse deform weights include vertex and group indices, preserving zeros.
    offsets, indices, weights = array("q", [0]), array("q"), array("d")
    for vertex in mesh.vertices:
        for group in vertex.groups:
            indices.append(group.group)
            weights.append(group.weight)
        offsets.append(len(indices))
    attributes = {a.name: _attribute(a) for a in mesh.attributes
                  if a.name != "material_index"}  # Material reassignment is authorized.
    settings = {key: _value(getattr(mesh, key)) for key in (
        "use_auto_smooth", "auto_smooth_angle", "use_mirror_x", "use_mirror_y",
        "use_mirror_z", "use_mirror_topology", "use_paint_mask", "use_paint_mask_vertex",
        "remesh_voxel_size", "remesh_voxel_adaptivity") if hasattr(mesh, key)}
    return {"id": _id(mesh), "settings": settings, "custom": _custom(mesh),
            "coordinates": _foreach(mesh.vertices, "co", 3),
            "edges": _foreach(mesh.edges, "vertices", 2, "q"),
            "loop_vertices": _foreach(mesh.loops, "vertex_index", code="q"),
            "loop_edges": _foreach(mesh.loops, "edge_index", code="q"),
            "polygon_loop_start": _foreach(mesh.polygons, "loop_start", code="q"),
            "polygon_loop_total": _foreach(mesh.polygons, "loop_total", code="q"),
            "polygon_smooth": _foreach(mesh.polygons, "use_smooth", code="b"),
            "has_custom_normals": mesh.has_custom_normals, "corner_normals": normals,
            "uv_order": [u.name for u in mesh.uv_layers],
            "uv_active_index": mesh.uv_layers.active_index, "uv_layers": uv,
            "attributes": attributes,
            "weights": {"offsets": _blob(offsets, "q"), "groups": _blob(indices, "q"), "values": _blob(weights)},
            "shape_keys": _shape_keys(mesh.shape_keys), "animation": _animation(mesh)}


def _pose_bone(bone):
    return {"settings": _rna(bone, skip={"bone", "parent", "children", "constraints",
                "id_data", "custom_shape_transform", "custom_shape", "bone_group"}),
            "parent": bone.parent.name if bone.parent else None,
            "custom_shape": _id(bone.custom_shape),
            "custom_shape_transform": bone.custom_shape_transform.name if bone.custom_shape_transform else None,
            "bone_group": getattr(getattr(bone, "bone_group", None), "name", None),
            "constraints": [_rna(c) for c in bone.constraints], "custom": _custom(bone),
            "matrix": _value(bone.matrix), "matrix_basis": _value(bone.matrix_basis)}


def _object(obj):
    row = {"id": _id(obj), "type": obj.type, "data": _id(obj.data),
           "parent": _id(obj.parent), "parent_type": obj.parent_type,
           "parent_bone": obj.parent_bone, "parent_vertices": list(obj.parent_vertices),
           "matrix_parent_inverse": _value(obj.matrix_parent_inverse),
           "matrix_basis": _value(obj.matrix_basis), "matrix_world": _value(obj.matrix_world),
           "location": _value(obj.location), "rotation_mode": obj.rotation_mode,
           "rotation_euler": _value(obj.rotation_euler), "rotation_quaternion": _value(obj.rotation_quaternion),
           "rotation_axis_angle": _value(obj.rotation_axis_angle), "scale": _value(obj.scale),
           "delta_location": _value(obj.delta_location), "delta_scale": _value(obj.delta_scale),
           "delta_rotation_euler": _value(obj.delta_rotation_euler),
           "delta_rotation_quaternion": _value(obj.delta_rotation_quaternion),
           "locks": {k: _value(getattr(obj, k)) for k in ("lock_location", "lock_rotation", "lock_rotation_w", "lock_rotations_4d", "lock_scale")},
           "collections": sorted(c.name for c in obj.users_collection),
           "vertex_groups": [{"name": g.name, "index": g.index, "lock_weight": g.lock_weight} for g in obj.vertex_groups],
           "constraints": [_rna(c) for c in obj.constraints],
           "modifiers": [{"settings": _rna(m), "custom": _custom(m)} for m in obj.modifiers],
           "custom": _custom(obj), "animation": _animation(obj)}
    for key in ("hide_render", "hide_viewport", "hide_select", "show_in_front",
                "display_type", "empty_display_type", "empty_display_size", "instance_type",
                "instance_collection", "active_shape_key_index", "show_only_shape_key"):
        if hasattr(obj, key):
            row[key] = _value(getattr(obj, key))
    if obj.type == "ARMATURE":
        row["pose_bones"] = {b.name: _pose_bone(b) for b in obj.pose.bones}
        row["pose_settings"] = _rna(obj.pose, skip={"bones", "bone_groups"})
        if hasattr(obj.pose, "bone_groups"):
            row["bone_groups"] = [_rna(g) for g in obj.pose.bone_groups]
    return row


def _armature(arm):
    bones = {}
    for bone in arm.bones:
        bones[bone.name] = {
            "settings": _rna(bone, skip={"parent", "children", "collections", "bbone_custom_handle_start", "bbone_custom_handle_end"}),
            "parent": bone.parent.name if bone.parent else None,
            "bbone_custom_handle_start": getattr(getattr(bone, "bbone_custom_handle_start", None), "name", None),
            "bbone_custom_handle_end": getattr(getattr(bone, "bbone_custom_handle_end", None), "name", None),
            "rest_matrix": _value(bone.matrix_local), "head": _value(bone.head_local),
            "tail": _value(bone.tail_local), "custom": _custom(bone),
            "collections": sorted(c.name for c in bone.collections) if hasattr(bone, "collections") else [],
        }
    return {"id": _id(arm), "settings": _rna(arm, skip={"bones", "edit_bones", "collections", "collections_all", "animation_data", "override_library", "asset_data", "library"}),
            "bones": bones, "bone_order": [b.name for b in arm.bones],
            "collections": [_rna(c, skip={"bones", "parent", "children"}) for c in arm.collections_all] if hasattr(arm, "collections_all") else [],
            "custom": _custom(arm), "animation": _animation(arm)}


def _action(action):
    # Generic RNA covers legacy fcurves and Blender 4.4+ layers/strips/channelbags.
    return {"id": _id(action), "settings": _rna(action, skip={"animation_data", "override_library", "asset_data", "library"}),
            "custom": _custom(action)}


def _geometry_nodes(tree):
    return {"id": _id(tree), "nodes": [_rna(n, skip={"internal_links", "parent"}) for n in tree.nodes],
            "links": [{"from_node": l.from_node.name, "from_socket": l.from_socket.identifier,
                       "to_node": l.to_node.name, "to_socket": l.to_socket.identifier,
                       "is_muted": l.is_muted} for l in tree.links],
            "custom": _custom(tree), "animation": _animation(tree)}


def snapshot(scene):
    """Return a JSON-safe protected-content snapshot of the open project.

    All bpy.data objects are covered, including original hidden/off-scene rig
    shapes. This function reads existing data and does not invoke save operators.
    An unsupported protected value raises; it cannot silently produce a pass.
    """
    import bpy
    if bpy.context.mode == "EDIT_MESH" or any(o.mode == "EDIT" for o in bpy.data.objects if hasattr(o, "mode")):
        raise RuntimeError("Snapshot requires object/pose mode; exit edit mode explicitly first")
    bpy.context.view_layer.update()
    content = {
        "scene": {"name": scene.name, "frame_current": scene.frame_current,
                  "frame_subframe": scene.frame_subframe, "frame_start": scene.frame_start,
                  "frame_end": scene.frame_end, "custom": _custom(scene),
                  "animation": _animation(scene)},
        "objects": {o.name: _object(o) for o in bpy.data.objects},
        "meshes": {m.name: _mesh(m) for m in bpy.data.meshes},
        "armatures": {a.name: _armature(a) for a in bpy.data.armatures},
        "actions": {a.name: _action(a) for a in bpy.data.actions},
        "cameras": {d.name: {"settings": _rna(d, skip={"animation_data", "override_library", "asset_data", "library"}), "custom": _custom(d), "animation": _animation(d)} for d in bpy.data.cameras},
        "lights": {d.name: {"settings": _rna(d, skip={"node_tree", "animation_data", "override_library", "asset_data", "library"}), "custom": _custom(d), "animation": _animation(d)} for d in bpy.data.lights},
        "curves": {d.name: {"settings": _rna(d, skip={"materials", "animation_data", "override_library", "asset_data", "library"}), "custom": _custom(d), "animation": _animation(d)} for d in bpy.data.curves},
        "collections": {c.name: {"custom": _custom(c), "hide_render": c.hide_render,
                                  "hide_viewport": c.hide_viewport, "hide_select": c.hide_select,
                                  "instance_offset": _value(c.instance_offset)} for c in bpy.data.collections},
        "geometry_node_groups": {n.name: _geometry_nodes(n) for n in bpy.data.node_groups if n.bl_idname == "GeometryNodeTree"},
    }
    return {"schema": SCHEMA, "blender_version": bpy.app.version_string,
            "sha256": _digest(content), "content": content}


def compare(before, after, *, atol=0.0, rtol=0.0, allowed_new_objects=(), max_differences=100):
    """Compare snapshots; exact by default, or explicit strict float tolerance.

    Integer/topology values never use float tolerance. A truncated detail list
    still counts every differing field. Accepted additions are listed separately.
    ``ok`` means every protected field passed, even when allowed additions make
    the overall hashes differ.
    """
    if atol < 0 or rtol < 0 or not math.isfinite(atol + rtol):
        raise ValueError("Tolerances must be finite nonnegative numbers")
    if before["schema"] != SCHEMA or after["schema"] != SCHEMA:
        raise ValueError("Unsupported snapshot schema")
    for item in (before, after):
        if _digest(item["content"]) != item["sha256"]:
            raise ValueError("Snapshot SHA256 mismatch")
    prior, current = before["content"], after["content"]
    object_names = set(allowed_new_objects)
    added_objects = set(current["objects"]) - set(prior["objects"])
    allowed_objects = {n for n in added_objects if n.startswith(_PREFIXES) or n in object_names}
    allowed_data = {(row["data"]["type"], row["data"]["name"]) for name, row in current["objects"].items()
                    if name in allowed_objects and row["data"]}
    allowed_geometry_nodes = set()
    for name in allowed_objects:
        if not name.startswith(_PREFIXES):
            continue
        for modifier in current["objects"][name].get("modifiers", []):
            settings = modifier.get("settings", {})
            group = settings.get("node_group")
            if (settings.get("type") == "NODES" and isinstance(group, dict)
                    and group.get("type") == "GeometryNodeTree"
                    and isinstance(group.get("name"), str)
                    and group["name"].startswith(_PREFIXES)):
                allowed_geometry_nodes.add(group["name"])
    differences, accepted = [], []
    counts = {"different_fields": 0, "tolerated_numeric_fields": 0}

    def add(path, kind, **details):
        counts["different_fields"] += 1
        if len(differences) < max_differences:
            differences.append({"path": list(path), "kind": kind, **details})

    def allowed(path):
        if len(path) == 2 and path[0] == "objects":
            return path[1] in allowed_objects
        if len(path) == 2 and path[0] == "collections":
            return path[1].startswith(_PREFIXES)
        if len(path) == 2 and path[0] == "geometry_node_groups":
            return path[1] in allowed_geometry_nodes
        if len(path) == 2 and path[0] in {"meshes", "cameras", "lights", "curves"}:
            row = current[path[0]][path[1]]
            # Camera.settings.type is PERSP/ORTHO, not the datablock RNA type.
            # Match the identity used by object.data, and still require the
            # data to belong to an explicitly permitted newly added object.
            type_name = row["id"]["type"] if "id" in row else row.get("settings", {}).get("rna_type")
            return (type_name, path[1]) in allowed_data
        if len(path) == 4 and path[:2] == ("scene", "custom") and path[2] in {"values", "ui"} and path[3] in {"huaxu_post_report", "render_device_policy"}:
            return True
        return len(path) == 4 and path[0] == "meshes" and path[2] == "attributes" and path[3] == "hx_source_color"

    def walk(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            if a.get("__numeric__") and b.get("__numeric__"):
                meta = ("typecode", "width", "count")
                if any(a[k] != b[k] for k in meta):
                    add(path, "numeric_layout", before={k: a[k] for k in meta}, after={k: b[k] for k in meta})
                    return
                if a["sha256"] == b["sha256"]:
                    return
                av, bv = _unblob(a), _unblob(b)
                is_float = a["typecode"] in {"d", "f"}
                bad, first, maximum = 0, None, 0.0
                for index, (x, y) in enumerate(zip(av, bv)):
                    delta = abs(x - y)
                    maximum = max(maximum, delta) if math.isfinite(delta) else float("inf")
                    same = x == y or (is_float and math.isfinite(x) and math.isfinite(y) and delta <= atol + rtol * max(abs(x), abs(y)))
                    if not same:
                        bad += 1
                        if first is None:
                            first = {"index": index, "element": index // a["width"], "component": index % a["width"], "before": _value(x), "after": _value(y)}
                if bad:
                    add(path, "numeric_values", changed_components=bad, maximum_absolute_difference=_value(maximum), first_difference=first)
                else:
                    counts["tolerated_numeric_fields"] += 1
                return
            for key in sorted(set(a) | set(b)):
                child = path + (key,)
                if key not in a:
                    if allowed(child):
                        accepted.append({"path": list(child), "reason": "authorized addition"})
                    else:
                        add(child, "unexpected_addition")
                elif key not in b:
                    add(child, "removed")
                else:
                    walk(a[key], b[key], child)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                add(path, "list_length", before=len(a), after=len(b))
            for index, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + (index,))
        elif a != b:
            if isinstance(a, float) and isinstance(b, (int, float)) and not isinstance(b, bool):
                delta = abs(a - b)
                if math.isfinite(delta) and delta <= atol + rtol * max(abs(a), abs(b)):
                    counts["tolerated_numeric_fields"] += 1
                else:
                    add(path, "value", before=a, after=b, absolute_difference=_value(delta))
            else:
                add(path, "value", before=a, after=b)

    walk(prior, current, ())
    return {"ok": counts["different_fields"] == 0, "before_sha256": before["sha256"],
            "after_sha256": after["sha256"], "exact_hash_match": before["sha256"] == after["sha256"],
            "atol": atol, "rtol": rtol, **counts, "differences": differences,
            "differences_truncated": counts["different_fields"] > len(differences),
            "accepted_additions": accepted}


def discover_controls(scene):
    """Return only genuinely existing controller bones; names are never created."""
    arms = [o for o in scene.objects if o.type == "ARMATURE" and o.pose]
    if not arms:
        return {"rig": None, "inventory": [], "controls": [], "reason": "no armature"}
    rig = max(arms, key=lambda o: (sum(b.custom_shape is not None for b in o.pose.bones), o.name.startswith("RIG-")))
    inventory = [{"name": b.name, "custom_shape": b.custom_shape.name if b.custom_shape else None,
                  "use_deform": b.bone.use_deform} for b in rig.pose.bones]
    controls = []
    candidates = {
        "head": ("head", "head_ctrl", "CTRL-head", "neck"),
        "arm": ("upper_arm_fk.L", "upper_arm_fk.R", "hand_ik.L", "hand_ik.R"),
        "finger": ("f_index.02.L", "f_index.01.L", "f_index.02.R", "f_middle.02.L"),
    }
    for label, names in candidates.items():
        name = next((n for n in names if n in rig.pose.bones and
                     (rig.pose.bones[n].custom_shape or not rig.pose.bones[n].bone.use_deform)), None)
        if name is None:
            continue
        spec = {"label": label, "rig": rig.name, "bone": name,
                "axis": 0, "angle_radians": 0.08, "property_overrides": []}
        if name.startswith("upper_arm_fk."):
            parent_name = "upper_arm_parent." + name.rsplit(".", 1)[1]
            parent = rig.pose.bones.get(parent_name)
            if parent and "IK_FK" in parent:
                spec["property_overrides"].append({"bone": parent_name, "property": "IK_FK", "value": 1.0})
        controls.append(spec)
    return {"rig": rig.name, "inventory": inventory, "controls": controls,
            "missing_categories": [k for k in candidates if k not in {s["label"] for s in controls}]}


def _pose_state(bone):
    return {"rotation_mode": bone.rotation_mode,
            "location": bone.location.copy(), "scale": bone.scale.copy(),
            "rotation_euler": bone.rotation_euler.copy(),
            "rotation_quaternion": bone.rotation_quaternion.copy(),
            "rotation_axis_angle": tuple(bone.rotation_axis_angle)}


def _restore_pose(bone, state):
    for key in ("location", "scale", "rotation_euler", "rotation_quaternion", "rotation_axis_angle"):
        setattr(bone, key, state[key])
    bone.rotation_mode = state["rotation_mode"]


def _update(rigs=()):
    import bpy
    for obj in rigs:
        obj.update_tag(refresh={"OBJECT"})
    bpy.context.view_layer.update()


def _sample(meshes, arms, control_rig=None, control_name=None):
    import bpy
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result = {"meshes": {}, "bones": {}, "control_matrix": None}
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            coordinates = array("d")
            for vertex in mesh.vertices:
                coordinates.extend(evaluated.matrix_world @ vertex.co)
            topology = array("q", [len(mesh.vertices), len(mesh.edges), len(mesh.polygons)])
            topology.extend(loop.vertex_index for loop in mesh.loops)
            result["meshes"][obj.name] = {"coordinates": coordinates,
                "topology": hashlib.sha256(topology.tobytes()).hexdigest()}
        finally:
            evaluated.to_mesh_clear()
    for arm in arms:
        evaluated = arm.evaluated_get(depsgraph)
        result["bones"][arm.name] = {b.name: tuple(v for row in evaluated.matrix_world @ b.matrix for v in row) for b in evaluated.pose.bones}
    if control_rig is not None:
        evaluated = control_rig.evaluated_get(depsgraph)
        result["control_matrix"] = tuple(v for row in evaluated.matrix_world @ evaluated.pose.bones[control_name].matrix for v in row)
    return result


def _response(initial, moved, movement_epsilon, bone_epsilon):
    meshes, bones = {}, {}
    for name, first in initial["meshes"].items():
        second = moved["meshes"].get(name)
        if second is None or first["topology"] != second["topology"]:
            meshes[name] = {"comparable": False, "reason": "evaluated topology changed"}
            continue
        a, b = first["coordinates"], second["coordinates"]
        maximum, sum_sq, count = 0.0, 0.0, 0
        displacement = array("d", (y - x for x, y in zip(a, b)))
        for index in range(0, len(a), 3):
            sq = sum((b[index + k] - a[index + k]) ** 2 for k in range(3))
            maximum = max(maximum, sq)
            sum_sq += sq
            count += sq > movement_epsilon ** 2
        vertices = len(a) // 3
        meshes[name] = {"comparable": True, "vertices": vertices,
                        "maximum_world_displacement": math.sqrt(maximum),
                        "rms_world_displacement": math.sqrt(sum_sq / max(1, vertices)),
                        "vertices_above_epsilon": count,
                        "world_displacement_vectors": _blob(displacement, width=3)}
    for name, first in initial["bones"].items():
        second = moved["bones"].get(name, {})
        deltas = {bone: max(abs(x - y) for x, y in zip(matrix, second[bone]))
                  for bone, matrix in first.items() if bone in second}
        bones[name] = {"maximum_matrix_component_difference": max(deltas.values(), default=0.0),
                       "bones_above_epsilon": sum(delta > bone_epsilon for delta in deltas.values()),
                       "per_bone_maximum_component_difference": deltas,
                       "bone_order": list(first),
                       "world_matrix_component_differences": _blob(
                           (y - x for bone, matrix in first.items() if bone in second
                            for x, y in zip(matrix, second[bone])), width=16),
                       "missing_bones": sorted(set(first) - set(second))}
    control_delta = max((abs(a - b) for a, b in zip(initial["control_matrix"] or (), moved["control_matrix"] or ())), default=0.0)
    comparable = all(v["comparable"] for v in meshes.values()) and all(not v["missing_bones"] for v in bones.values())
    skin = any(v.get("vertices_above_epsilon", 0) for v in meshes.values())
    native = any(v["bones_above_epsilon"] for v in bones.values())
    return {"comparable": comparable, "skin_responded": bool(skin), "native_bones_responded": bool(native),
            "control_evaluated_matrix_difference": control_delta, "meshes": meshes, "native_armatures": bones}


def _probe_baseline_comparison(previous, current, atol, rtol):
    """A response mismatch is a regression; inherited silence is not a pass."""
    if previous.get("status") in {"error", "missing_control", "not_testable"} or current.get("status") in {"error", "missing_control", "not_testable"}:
        return {"classification": "not_comparable", "ok": False}
    a, b = previous["response"], current["response"]
    if not a["comparable"] or not b["comparable"]:
        return {"classification": "topology_or_bone_mismatch", "ok": False}
    differences = []
    for group, field in (("meshes", "maximum_world_displacement"), ("native_armatures", "maximum_matrix_component_difference")):
        if set(a[group]) != set(b[group]):
            differences.append({"group": group, "reason": "targets changed"})
        for name in sorted(set(a[group]) & set(b[group])):
            av, bv = a[group][name][field], b[group][name][field]
            if abs(av - bv) > atol + rtol * max(abs(av), abs(bv)):
                differences.append({"group": group, "name": name, "field": field, "before": av, "after": bv, "absolute_difference": abs(av - bv)})
            vector_field = "world_displacement_vectors" if group == "meshes" else "world_matrix_component_differences"
            avectors, bvectors = a[group][name][vector_field], b[group][name][vector_field]
            if avectors["count"] != bvectors["count"]:
                differences.append({"group": group, "name": name, "reason": "response vector lengths changed"})
            elif avectors["sha256"] != bvectors["sha256"]:
                maximum, changed, first = 0.0, 0, None
                for index, (x, y) in enumerate(zip(_unblob(avectors), _unblob(bvectors))):
                    delta = abs(x - y)
                    maximum = max(maximum, delta)
                    if delta > atol + rtol * max(abs(x), abs(y)):
                        changed += 1
                        if first is None:
                            first = {"component_index": index, "before": x, "after": y}
                if changed:
                    differences.append({"group": group, "name": name, "field": vector_field,
                                        "changed_components": changed,
                                        "maximum_absolute_difference": maximum, "first_difference": first})
        if group == "native_armatures":
            for name in sorted(set(a[group]) & set(b[group])):
                x = a[group][name]["per_bone_maximum_component_difference"]
                y = b[group][name]["per_bone_maximum_component_difference"]
                if set(x) != set(y):
                    differences.append({"group": group, "name": name, "reason": "bone target set changed"})
                for bone in sorted(set(x) & set(y)):
                    if abs(x[bone] - y[bone]) > atol + rtol * max(abs(x[bone]), abs(y[bone])):
                        differences.append({"group": group, "name": name, "bone": bone, "before": x[bone], "after": y[bone], "absolute_difference": abs(x[bone] - y[bone])})
    if differences or any(a[k] != b[k] for k in ("skin_responded", "native_bones_responded")):
        classification, ok = "response_regression_or_change", False
    elif not a["skin_responded"] and not a["native_bones_responded"]:
        classification, ok = "inherited_no_observed_native_response", True
    elif not a["skin_responded"]:
        classification, ok = "inherited_bone_response_without_skin_response", True
    else:
        classification, ok = "preserved_observed_response", True
    return {"classification": classification, "ok": ok, "differences": differences,
            "note": "ok means preserved relative to baseline; it does not assert that an originally nonresponsive rig is bound or functional."}


def probe_controls(scene, *, baseline=None, controls=None, movement_epsilon=1e-7,
                   bone_epsilon=1e-8, response_atol=1e-7, response_rtol=1e-6,
                   verify_restoration=True):
    """Rotate observed controls 0.08 rad, measure native skin/bones, then restore.

    ``controls`` is a list from discover_controls()["controls"]. When a baseline
    is supplied, its exact recorded controls/targets are reused. Small FK mode
    overrides are explicitly recorded and restored, never saved or repaired.
    Measurements are scene world units, not assumed metres. Baseline silence
    is reported as observed silence, not proof of missing binding or success.
    """
    import bpy
    from mathutils import Quaternion
    if any(v < 0 or not math.isfinite(v) for v in (movement_epsilon, bone_epsilon, response_atol, response_rtol)):
        raise ValueError("Probe tolerances must be finite and nonnegative")
    observed = discover_controls(scene)
    specifications = controls if controls is not None else (baseline["control_specs"] if baseline else observed["controls"])
    specifications = json.loads(json.dumps(specifications))
    before = snapshot(scene) if verify_restoration else None
    rigs = {spec["rig"] for spec in specifications}
    if baseline:
        mesh_names = baseline["targets"]["meshes"]
        arm_names = baseline["targets"]["native_armatures"]
    else:
        mesh_names, arm_names = [], set()
        for obj in scene.objects:
            if obj.type != "MESH":
                continue
            bound = [m.object for m in obj.modifiers if m.type == "ARMATURE" and m.object and m.show_viewport]
            if bound:
                mesh_names.append(obj.name)
                arm_names.update(arm.name for arm in bound)
        arm_names = sorted(arm_names)
        mesh_names.sort()
    # Native target means the armature actually used by a mesh modifier. It may
    # legitimately be the control rig itself; no naming convention substitutes.
    meshes = [bpy.data.objects[n] for n in mesh_names if n in bpy.data.objects]
    arms = [bpy.data.objects[n] for n in arm_names if n in bpy.data.objects]
    missing_targets = [n for n in mesh_names + list(arm_names) if n not in bpy.data.objects]
    rows = []
    for spec in specifications:
        row = {"label": spec["label"], "rig": spec["rig"], "control": spec["bone"], "spec": spec}
        rig = bpy.data.objects.get(spec["rig"])
        bone = rig.pose.bones.get(spec["bone"]) if rig and rig.type == "ARMATURE" else None
        if bone is None:
            row.update(status="missing_control", error="Recorded control is absent")
            rows.append(row)
            continue
        if not meshes or missing_targets:
            row.update(status="not_testable", error="No bound mesh or recorded native target is absent")
            rows.append(row)
            continue
        axis = spec.get("axis", 0)
        angle = spec.get("angle_radians", 0.08)
        if axis not in (0, 1, 2) or not math.isfinite(angle) or abs(angle) > 0.25:
            raise ValueError("Probe must use a valid axis and a rotation no larger than 0.25 radians")
        state = _pose_state(bone)
        properties = []
        restoration_sample = None
        try:
            _update([rig] + arms)
            unmodified = _sample(meshes, arms, rig, bone.name)
            for override in spec.get("property_overrides", []):
                owner = rig.pose.bones.get(override["bone"])
                if owner is None or override["property"] not in owner:
                    raise ValueError("Recorded FK/property override is absent")
                key = override["property"]
                properties.append((owner, key, owner[key]))
                owner[key] = override["value"]
            _update([rig] + arms)
            initial = _sample(meshes, arms, rig, bone.name)
            if bone.rotation_mode == "QUATERNION":
                rotation = bone.rotation_quaternion.copy()
            elif bone.rotation_mode == "AXIS_ANGLE":
                aa = bone.rotation_axis_angle
                rotation = Quaternion(aa[1:], aa[0]) if any(aa[1:]) else Quaternion()
            else:
                rotation = bone.rotation_euler.to_quaternion()
            vector = [0.0, 0.0, 0.0]
            vector[axis] = 1.0
            bone.rotation_mode = "QUATERNION"
            bone.rotation_quaternion = rotation @ Quaternion(vector, angle)
            _update([rig] + arms)
            moved = _sample(meshes, arms, rig, bone.name)
            response = _response(initial, moved, movement_epsilon, bone_epsilon)
            row["response"] = response
            row["status"] = ("skin_response_observed" if response["skin_responded"] else
                             "native_bone_response_only" if response["native_bones_responded"] else
                             "no_observed_native_response")
        except Exception as exc:
            row.update(status="error", error=type(exc).__name__ + ": " + str(exc))
        finally:
            _restore_pose(bone, state)
            for owner, key, value in reversed(properties):
                owner[key] = value
            _update([rig] + arms)
            if "unmodified" in locals():
                restoration_sample = _response(unmodified, _sample(meshes, arms, rig, bone.name), movement_epsilon, bone_epsilon)
                row["restoration_response"] = restoration_sample
                row["restored_evaluated_state"] = restoration_sample["comparable"] and not restoration_sample["skin_responded"] and not restoration_sample["native_bones_responded"] and restoration_sample["control_evaluated_matrix_difference"] <= bone_epsilon
                del unmodified
        if baseline:
            previous = next((p for p in baseline["probes"] if p["rig"] == row["rig"] and p["control"] == row["control"] and p["label"] == row["label"]), None)
            row["baseline_comparison"] = _probe_baseline_comparison(previous, row, response_atol, response_rtol) if previous else {"classification": "missing_baseline", "ok": False}
        rows.append(row)
    restoration = compare(before, snapshot(scene)) if verify_restoration else None
    all_restored = bool(rows) and all(r.get("restored_evaluated_state", False) for r in rows)
    evaluated = bool(rows) and all(r["status"] not in {"error", "missing_control", "not_testable"} for r in rows)
    preservation = all(r.get("baseline_comparison", {}).get("ok", False) for r in rows) if baseline else None
    context_matches = (baseline["scene"] == scene.name and baseline["frame"] == scene.frame_current
                       and baseline["frame_subframe"] == scene.frame_subframe
                       and baseline["control_specs"] == specifications) if baseline else None
    if baseline:
        preservation = bool(rows) and preservation and context_matches
    return {"schema": "huaxu-controller-probe-v1", "scene": scene.name,
            "frame": scene.frame_current, "frame_subframe": scene.frame_subframe,
            "units": "scene world units", "movement_epsilon": movement_epsilon,
            "bone_epsilon": bone_epsilon, "response_atol": response_atol, "response_rtol": response_rtol,
            "discovery": observed, "control_specs": specifications,
            "targets": {"meshes": mesh_names, "native_armatures": list(arm_names)},
            "missing_targets": missing_targets, "probes": rows,
            "all_probes_evaluated": evaluated, "all_evaluated_states_restored": all_restored,
            "protected_state_restoration": restoration,
            "baseline_response_preserved": preservation,
            "baseline_context_matches": context_matches,
            "all_tested_controls_move_skin": bool(rows) and all(r.get("response", {}).get("skin_responded", False) for r in rows),
            "no_scene_save_performed": True,
            "note": "No observed response is a measurement, not a successful binding test. A matching baseline documents an inherited limitation; no rig repair is attempted."}
