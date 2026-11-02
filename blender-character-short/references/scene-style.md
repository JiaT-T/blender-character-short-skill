# Optional scene matte bands

Choose the environment's palette, shapes, scale, edges and light around the
character and plot first. The optional shader mix below is a scene adaptation,
not a substitute for that design or a character/source-shader reproduction.

```json
{
  "set": {
    "matte_style": {
      "mix": 0.35,
      "stage": ["floor"],
      "story": ["ivory", "slate", "socket"]
    }
  }
}
```

Merge this field into a complete set input. `stage` selects the built-in
`floor`, `panel` or `trim` keys. `story` selects actual keys in `set.materials`.
There are no character names or inferred material-name matches in the route.
Omitting the option performs no material mutation. Mix zero also preserves all
nodes and links after validating the selection. Values must be finite within
0..1. Both lists contain distinct existing names; select at least one material.

The builder validates the whole selection before changing any selected graph.
It refuses character-shared materials, animation, emission, transmission,
transparency, linked base colors and unsupported surface graphs. Keep metal,
animated feedback and character surfaces on their original shaders. The output
build report records the exact selected material keys, colors and mix.

In Eevee, diffuse illumination is reduced to three constant light levels and
multiplied by the explicit base color. The result mixes with the original
Principled surface. A modest mix can simplify broad matte surfaces while the
original component retains some depth, shadow and specular variation. Larger
mixes can flatten contact shadows and make light thresholds jump in motion.

Compare original and candidate at identical frames/cameras, resolution, samples
and external post settings. Actually inspect the support/contact shadow,
feedback weak/off/steady states, character separation and moving thresholds.
Preserve the original complete preview until a complete candidate has been
checked. Integer-frame geometry and an unchanged emission value do not prove
the result is readable or temporally stable. Record sampled review, numerical
temporal diagnostics and continuous viewing separately.

This route is Eevee-only. It does not implement source outlines, iris optics,
transparent materials, arbitrary texture shaders or website GPU equivalence.
