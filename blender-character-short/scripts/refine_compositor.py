"""Refine an existing Huaxu-style compositor without replacing its main color path.

No file I/O, rendering or private assets. The caller owns a backed-up scene and
must save/reopen/validate it. This is a narrow adapter, not a generic look builder.
"""
from __future__ import annotations

import math

DEFAULTS = {
    "premultiply_node": "HuaxuPost_Premultiplied to straight",
    "glare_node": "HuaxuPost_Approximate weighted Fog Glow",
    "gain_nodes": ["HuaxuPost_Conservative Bloom gain " + str(i) for i in range(3)],
    "prefix": "RefineBloom_",
    "coverage": True,
    "gain": 0.025,
    "device": "GPU",
    "precision": "FULL",
}


def normalized_config(config=None):
    config = {} if config is None else config
    if not isinstance(config, dict) or set(config) - set(DEFAULTS):
        raise ValueError("Unknown compositor refinement configuration")
    result = dict(DEFAULTS, **config)
    for key in ("premultiply_node", "glare_node", "prefix"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError("Nonempty node names/prefix required")
    if len(result["prefix"]) > 40:
        raise ValueError("Refinement prefix must be at most 40 characters")
    names = result["gain_nodes"]
    if not isinstance(names, list) or len(names) != 3 or not all(isinstance(n, str) and n for n in names) or len(set(names)) != 3:
        raise ValueError("Three distinct RGB gain nodes required")
    if len(set([result["premultiply_node"], result["glare_node"], *names])) != 5:
        raise ValueError("Input node selectors must be distinct")
    if type(result["coverage"]) is not bool:
        raise ValueError("coverage must be boolean")
    gain = result["gain"]
    if type(gain) not in (int, float) or not math.isfinite(gain) or not 0 <= gain <= 1:
        raise ValueError("gain must be finite and within 0..1")
    if result["device"] not in ("CPU", "GPU") or result["precision"] not in ("AUTO", "FULL"):
        raise ValueError("Unsupported compositor execution settings")
    return result


def _one_link(socket, description):
    if len(socket.links) != 1:
        raise ValueError(description + " must have exactly one input link")
    return socket.links[0]


def _link_key(link):
    return (link.from_node.name, list(link.from_node.outputs).index(link.from_socket),
            link.to_node.name, list(link.to_node.inputs).index(link.to_socket))


def _node_state(node):
    from saved_look import node_properties, socket_value
    return {"type": node.bl_idname, "properties": node_properties(node),
            "inputs": [socket_value(s) for s in node.inputs],
            "mute": node.mute, "image": getattr(getattr(node, "image", None), "name", None),
            "group": getattr(getattr(node, "node_tree", None), "name", None)}


def apply(scene, config=None):
    """Install explicit coverage/gain controls; reject unsupported input topology.

    The coverage encode intentionally reproduces the tested approximation
    1.055 * max(premultiplied RGB, 0) ** (1/2.4) - 0.055, alpha=1.
    It is not the website's exact MRT bloom nor a general-purpose sRGB transform.
    coverage=False preserves the original glare source via a labeled switch.
    """
    cfg = normalized_config(config)
    tree = getattr(scene, "node_tree", None)
    if not getattr(scene, "use_nodes", False) or tree is None:
        raise ValueError("Existing enabled compositor required")
    if any(n.name.startswith(cfg["prefix"]) for n in tree.nodes):
        raise ValueError("Refinement prefix already exists; use an untouched source copy")
    if not getattr(scene.render, "use_compositing", False):
        raise ValueError("Scene compositing must already be enabled")
    for prop, value in (("compositor_device", cfg["device"]), ("compositor_precision", cfg["precision"])):
        if not hasattr(scene.render, prop):
            raise ValueError("Blender lacks " + prop)
        items = scene.render.bl_rna.properties[prop].enum_items.keys()
        if value not in items:
            raise ValueError("Unsupported " + prop + ": " + value)
    premul = tree.nodes.get(cfg["premultiply_node"])
    glare = tree.nodes.get(cfg["glare_node"])
    gains = [tree.nodes.get(name) for name in cfg["gain_nodes"]]
    if premul is None or premul.bl_idname != "CompositorNodePremulKey" or premul.mapping != "PREMUL_TO_STRAIGHT" or premul.mute:
        raise ValueError("Expected active premultiplied-to-straight node")
    if glare is None or glare.bl_idname != "CompositorNodeGlare" or glare.glare_type != "FOG_GLOW" or glare.mute:
        raise ValueError("Expected active Fog Glow node")
    raw_link = _one_link(premul.inputs[0], "Premultiplied input")
    glare_link = _one_link(glare.inputs["Image"], "Fog Glow input")
    for node in gains:
        if node is None or node.bl_idname != "CompositorNodeMath" or node.operation != "MULTIPLY" or node.mute:
            raise ValueError("Expected active RGB multiply gain nodes")
        _one_link(node.inputs[0], "Gain color input")
        if node.inputs[1].is_linked or not node.outputs[0].is_linked:
            raise ValueError("Gain must have constant factor and connected output; already refined inputs are rejected")
    # Reject unreachable adapters: all modified nodes must feed the active output.
    outputs = [n for n in tree.nodes if n.bl_idname == "CompositorNodeComposite" and getattr(n, "is_active_output", True)]
    if len(outputs) != 1:
        raise ValueError("One active Composite output required")
    reachable = set()
    def walk(node):
        if node.name in reachable:
            return
        reachable.add(node.name)
        for socket in node.inputs:
            for link in socket.links:
                walk(link.from_node)
    walk(outputs[0])
    if any(n.name not in reachable for n in [premul, glare, *gains]):
        raise ValueError("Selected compositor nodes do not reach active Composite")
    before_nodes = {n.name: _node_state(n) for n in tree.nodes}
    before_links = {_link_key(l) for l in tree.links}
    replaced_link = _link_key(glare_link)
    raw = raw_link.from_socket
    original = glare_link.from_socket
    before_execution = {k: getattr(scene.render, k) for k in ("compositor_device", "compositor_precision")}
    old_gains = [float(n.inputs[1].default_value) for n in gains]
    made = []
    def new(kind, label):
        node = tree.nodes.new(kind)
        made.append(node)
        node.name = cfg["prefix"] + label
        if node.name != cfg["prefix"] + label:
            raise ValueError("Node naming collision")
        node.label = label
        if len(made) > 1:
            node.parent = made[0]
            node.location = (((len(made)-2)//8)*190, -((len(made)-2)%8)*140)
        return node
    def binary(op, a, b, name):
        node = new("CompositorNodeMath", name)
        node.operation = op
        for value, sock in zip((a, b), node.inputs):
            if hasattr(value, "node"):
                tree.links.new(value, sock)
            else:
                sock.default_value = value
        return node.outputs[0]
    try:
        frame = new("NodeFrame", "Controls")
        frame.label = "Coverage-aware bloom only; main curve and LUT preserved"
        split = new("CompositorNodeSeparateColor", "Premultiplied RGB")
        split.mode = "RGB"
        tree.links.new(raw, split.inputs[0])
        encoded = []
        for i in range(3):
            value = binary("MAXIMUM", split.outputs[i], 0, "Nonnegative " + str(i))
            value = binary("POWER", value, 1/2.4, "Encode power " + str(i))
            value = binary("MULTIPLY", value, 1.055, "Encode scale " + str(i))
            encoded.append(binary("SUBTRACT", value, .055, "Encode offset " + str(i)))
        combine = new("CompositorNodeCombineColor", "Coverage encoded source")
        combine.mode = "RGB"
        for i, value in enumerate(encoded):
            tree.links.new(value, combine.inputs[i])
        combine.inputs[3].default_value = 1
        coverage = new("CompositorNodeValue", "Coverage correction")
        coverage.outputs[0].default_value = float(cfg["coverage"])
        switch = new("CompositorNodeMixRGB", "Original or coverage source")
        switch.blend_type = "MIX"
        switch.use_clamp = False
        tree.links.new(coverage.outputs[0], switch.inputs[0])
        tree.links.new(original, switch.inputs[1])
        tree.links.new(combine.outputs[0], switch.inputs[2])
        tree.links.new(switch.outputs[0], glare.inputs["Image"])
        gain = new("CompositorNodeValue", "Bloom gain")
        gain.outputs[0].default_value = cfg["gain"]
        for node in gains:
            tree.links.new(gain.outputs[0], node.inputs[1])
        scene.render.compositor_device = cfg["device"]
        scene.render.compositor_precision = cfg["precision"]
        if before_nodes != {name: _node_state(tree.nodes[name]) for name in before_nodes}:
            raise ValueError("Original compositor node settings unexpectedly changed")
        old_links_after = {_link_key(l) for l in tree.links
                           if l.from_node.name in before_nodes and l.to_node.name in before_nodes}
        if old_links_after != before_links - {replaced_link}:
            raise ValueError("Original compositor links unexpectedly changed")
        return {"adapter": "coverage-bloom-v1", "config": cfg,
                "created_nodes": [n.name for n in made],
                "coverage_control": coverage.name, "gain_control": gain.name,
                "original_gain_values": old_gains, "original_execution": before_execution,
                "original_glare_link": list(replaced_link),
                "preserved_original_nodes": len(before_nodes),
                "preserved_original_links": len(old_links_after),
                "materials_modified": False, "main_curve_lut_replaced": False,
                "rendered": False, "temporal_validation": False}
    except Exception:
        for node in reversed(made):
            tree.nodes.remove(node)
        tree.links.new(original, glare.inputs["Image"])
        for key, value in before_execution.items():
            setattr(scene.render, key, value)
        raise


apply_refinement = apply
