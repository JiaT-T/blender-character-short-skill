# Source-derived SMAA integration

Use this only when the reference source selects the corresponding SMAA implementation. It is an explicit alternative after the source Bloom/curve/LUT stage, not a generic aesthetic filter. Current CPU tests and two-character sequences passed; full website GPU numerical equivalence remains unverified.

`post_sequence.py` and `run_short.py` accept paired `--smaa-area AREA.png --smaa-search SEARCH.png`. Supply the source-version-matched lookup resources externally; they are not included in this skill. The tested resources are Area 160×560 RGB and Search 66×33 grayscale, extracted from the documented source bundle. Record their hashes and provenance with the production inputs.

The sequence wrapper passes `source_post.process(...)[web_premultiplied][::-1]`: top-down, display-encoded, premultiplied RGBA8. The three CPU stages are edges, weights and neighborhood blend. Edge/weight RT writes round-trip through float16. The source alpha-aware edge color, lookup filtering, eight-step search, shader offset conversion and gamma-space neighborhood behavior are retained; do not replace these with a standard SMAA port without checking the actual shader variant.

The first requested frame starts with an explicitly fresh zero edge target. Subsequent frames reuse previous edges because the observed source does not clear that target. A start other than frame 1 establishes a new history; it does not recreate the omitted earlier frames. Preserve history through camera cuts when the source retains the same targets. Unknown website frame history remains an input mismatch.

Each frame commits its PNG, compressed half-float edge state and a JSON record binding raw bytes, script/profile/lookup identity, PNG bytes, edge bytes and predecessor state. Resume by repeating the exact same command. Corrupt or missing PNG/edge records are recomputed from the last validated history. A new script, AA mode, lookup or requested range requires a new output version. Do not copy a PNG alone and claim the temporal state is recoverable.

The new pipeline also binds `preview.mp4` to the ordered PNG hashes and encoder settings in `preview-frame-signature.json`. A stale or unsigned existing video is rejected and preserved; use a new version instead of overwriting the evidence.

Validated scope: two 192-frame, 640×360, 24fps sequences; real termination at frame24 followed by corrupt/missing edge and altered PNG recovery, all192 outputs and states identical to a clean run; default no-AA four-frame pixel regression; actual encoding and12 video-binding checks. These are CPU/encoding results. The complete updated `run_short` entrypoint needs its own versioned raw-PMX run before being called end-to-end validated.

For visual review keep no-AA and AA outputs, inspect actual edge/costume/face samples and look for regressions. Pixel differences only prove processing occurred. The preserved website captures have sparse byte samples rather than full-size composite and floating stages, so they cannot establish CPU-to-GPU numerical parity. Obtain matched complete inputs and edge history before promoting that gate.
