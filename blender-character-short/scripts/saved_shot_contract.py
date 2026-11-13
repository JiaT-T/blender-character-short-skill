"""Bind a shot declaration to an already-open saved Blender scene.

No opening, saving, rendering, scene repair, or Blender launch occurs here.
Host tests can inject ``depsgraph_getter``; bpy is imported lazily only when
evaluated object samples are requested without that explicit provider.
"""
import hashlib
import json
import math

from shot_plan import validate


FPS_BASE_ABS_TOLERANCE = 1e-7  # Blender stores fps_base as a float property.
MAX_OBJECT_MATRIX_SAMPLES = 100000


def _digest(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Shot plan must be finite JSON data") from exc
    return hashlib.sha256(raw).hexdigest()


def _object(scene, name, camera=False):
    obj = scene.objects.get(name)
    if obj is None or obj.name != name:
        raise ValueError("Exact scene object missing: " + name)
    if camera and obj.type != "CAMERA":
        raise ValueError("Shot camera is not a CAMERA object: " + name)
    return obj


def _matrix(value):
    try:
        rows = [[float(x) for x in row] for row in value]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Evaluated world transform must be a finite 4x4 matrix") from exc
    if len(rows) != 4 or any(len(row) != 4 for row in rows) or not all(
            math.isfinite(x) for row in rows for x in row):
        raise ValueError("Evaluated world transform must be a finite 4x4 matrix")
    return rows


def _depsgraph(scene, getter):
    if getter is not None:
        graph = getter()
    else:
        import bpy
        if bpy.context.scene != scene:
            raise ValueError("Sampling another scene requires an explicit depsgraph_getter")
        graph = bpy.context.evaluated_depsgraph_get()
    if graph is None:
        raise ValueError("Evaluated object sampling requires a dependency graph")
    evaluated_scene = getattr(graph, "scene_eval", None)
    if evaluated_scene is None or getattr(evaluated_scene, "original", evaluated_scene) != scene:
        raise ValueError("Sampling dependency graph must belong to the validated scene")
    graph.update()
    return graph


def validate_scene_shots(scene, plan, *, display_range=None,
                         object_bindings=None, depsgraph_getter=None):
    """Validate camera markers and optionally observe objects across hard cuts.

    ``display_range=(first,last)`` is the render job's inclusive display range;
    when omitted the validated plan range is the display range. The scene may
    include preroll/postroll. Preview-range UI settings do not define display.

    ``object_bindings`` maps declared asset IDs to exact scene object names.
    It can instead be supplied as the plan's optional top-level object_bindings.
    Hard-cut samples are the previous shot's last frame and incoming shot's
    first frame, [cut-1,cut]. Movement is reported without acceptance thresholds.
    The caller's frame, subframe, and camera are restored even on sampling error.
    """
    declared = validate(plan)
    plan_sha256 = _digest(plan)
    first, last = plan["start"], plan["end"]
    if display_range is None:
        display_range = (first, last)
    if not isinstance(display_range, (tuple, list)) or len(display_range) != 2 or any(
            type(x) is not int for x in display_range) or tuple(display_range) != (first, last):
        raise ValueError("Shot plan range must equal the specified inclusive display range")
    if type(scene.frame_start) is not int or type(scene.frame_end) is not int or not (
            scene.frame_start <= first <= last <= scene.frame_end):
        raise ValueError("Saved scene range must contain the complete display range")
    fps, base = scene.render.fps, scene.render.fps_base
    if type(fps) is not int or fps != plan["fps"]:
        raise ValueError("Saved scene fps differs from the shot plan")
    if isinstance(base, bool) or not isinstance(base, (int, float)) or not math.isfinite(base) or not math.isclose(
            base, plan.get("fps_base", 1.0), rel_tol=0, abs_tol=FPS_BASE_ABS_TOLERANCE):
        raise ValueError("Saved scene fps_base differs from the shot plan (absolute tolerance 1e-7)")
    if scene.camera is None or _object(scene, scene.camera.name, camera=True) != scene.camera:
        raise ValueError("Saved active camera must be a CAMERA object in this scene")

    shots = plan["shots"]
    cameras = {s["camera"]: _object(scene, s["camera"], camera=True) for s in shots}
    markers = {}
    ignored_markers = 0
    for marker in scene.timeline_markers:
        if marker.camera is None:
            continue
        if type(marker.frame) is not int:
            raise ValueError("Camera marker frame must be an integer")
        if not first <= marker.frame <= last:
            ignored_markers += 1
            continue
        if marker.frame in markers:
            raise ValueError("Ambiguous multiple camera markers at frame " + str(marker.frame))
        if _object(scene, marker.camera.name, camera=True) != marker.camera:
            raise ValueError("Camera marker target is outside this scene")
        markers[marker.frame] = marker
    shot_rows = []
    for shot in shots:
        marker = markers.get(shot["start"])
        if marker is None or marker.camera != cameras[shot["camera"]]:
            raise ValueError("Shot start requires its exact camera marker: " + shot["id"])
        shot_rows.append({"id": shot["id"], "start": shot["start"], "end": shot["end"],
                          "camera": shot["camera"], "marker_name": marker.name})
    index, redundant = 0, []
    starts = {s["start"] for s in shots}
    for frame, marker in sorted(markers.items()):
        while frame > shots[index]["end"]:
            index += 1
        if marker.camera != cameras[shots[index]["camera"]]:
            raise ValueError("Unplanned camera switch within shot at frame " + str(frame))
        if frame not in starts:
            redundant.append({"frame": frame, "camera": marker.camera.name, "marker_name": marker.name})

    supplied = plan.get("object_bindings", {})
    if object_bindings is None:
        object_bindings = supplied
    elif "object_bindings" in plan and object_bindings != supplied:
        raise ValueError("Explicit object_bindings conflict with the shot plan")
    assets = plan.get("assets", {})
    if not isinstance(object_bindings, dict) or any(
            not isinstance(k, str) or k not in assets or not isinstance(v, str) or not v.strip()
            for k, v in object_bindings.items()):
        raise ValueError("object_bindings must map known asset IDs to exact object names")
    bindings = {k: _object(scene, v) for k, v in sorted(object_bindings.items())}
    cuts = declared["expected_cut_frames"]
    frames = sorted({f for cut in cuts for f in (cut - 1, cut)}) if bindings else []
    sample_count = len(frames) * len(bindings)
    if sample_count > MAX_OBJECT_MATRIX_SAMPLES:
        raise ValueError("Object transform observations exceed explicit 100000 matrix sample budget")
    snapshots = {}
    original_frame, original_subframe, original_camera = scene.frame_current, scene.frame_subframe, scene.camera
    sampling_started = False
    try:
        for frame in frames:
            sampling_started = True
            scene.frame_set(frame, subframe=0.0)
            graph = _depsgraph(scene, depsgraph_getter)
            snapshots[frame] = {key: _matrix(obj.evaluated_get(graph).matrix_world)
                                for key, obj in bindings.items()}
    finally:
        # frame_set itself can apply a timeline camera switch. Restore camera last.
        if sampling_started:
            try:
                scene.frame_set(original_frame, subframe=original_subframe)
            finally:
                scene.camera = original_camera
    movements = []
    for cut in cuts:
        for key, obj in bindings.items():
            before, after = snapshots[cut - 1][key], snapshots[cut][key]
            translation = math.dist([after[i][3] for i in range(3)],
                                    [before[i][3] for i in range(3)])
            component = max(abs(after[i][j] - before[i][j]) for i in range(4) for j in range(4))
            if not math.isfinite(translation) or not math.isfinite(component):
                raise ValueError("Observed movement must be finite")
            movements.append({"asset_id": key, "object_name": obj.name, "cut_frame": cut,
                              "frames": [cut - 1, cut], "world_before": before, "world_after": after,
                              "translation_distance_scene_units": translation,
                              "max_matrix_component_change": component})
    return {"schema": "saved-shot-contract-v1", "valid_scene_binding": True,
            "plan_sha256": plan_sha256, "declaration": declared,
            "scene_name": getattr(scene, "name", None), "initial_camera": original_camera.name,
            "scene_range": [scene.frame_start, scene.frame_end], "display_range": [first, last],
            "fps": fps, "fps_base": base, "fps_base_abs_tolerance": FPS_BASE_ABS_TOLERANCE,
            "shots": shot_rows, "redundant_same_camera_markers": redundant,
            "observed_camera_markers": [{"frame": f, "camera": m.camera.name, "marker_name": m.name}
                                        for f, m in sorted(markers.items())],
            "camera_markers_outside_display_ignored": ignored_markers,
            "object_bindings": {k: obj.name for k, obj in bindings.items()},
            "observed_cut_movements": movements, "sample_frames": frames, "object_matrix_samples": sample_count,
            "max_object_matrix_samples": MAX_OBJECT_MATRIX_SAMPLES,
            "movement_rejection_thresholds": None, "visual_acceptance": False,
            "normal_speed_continuous_viewing": False,
            "scope": "Saved scene range/rate, exact scene cameras and timeline marker coverage. "
                     "Optional evaluated object matrices at [cut-1,cut] only; movement is descriptive. "
                     "No saved-file hash/reopen, rendered pixels, runtime handlers, acting naturalness, "
                     "contact, attachment, collision, friction, or continuous-motion certification."}
