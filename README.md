# OBJ 2.0

A Blender add-on that exports Wavefront `.obj` extended with **vertex colors**,
**Blender lights**, and a second **UV layer** for lightmaps. The output is
still valid OBJ — other importers just see normal geometry.

## Install

Blender → **Edit → Preferences → Add-ons → Install…** → `obj2_export.py`, then
export via **File → Export → OBJ 2.0 (.obj)**.

## Vertex colors

The active color attribute rides each vertex line:

```
v x y z r g b
```

0..1 floats by default (0..255 optional). POINT and CORNER domains both work;
meshes without colors write plain `v x y z`.

## Blender lights

Point and sun lamps plus the world ambient export as comment lines, through
the same Forward/Up axis conversion as the geometry:

```
#ambient r g b                        (world color × strength)
#light   x y z  r g b  energy radius  (point; radius = Custom Distance, 0 = none)
#sun     dx dy dz  r g b  strength    (direction the light travels)
```

## UV layers (lightmaps & AO maps)

Extra UV layers ride the same `vt` line as extra pairs — pair 2 = lightmap
(layer named `Lightmap`), pair 3 = grayscale AO (layer named `AO`). The
**Lightmap PNG** / **AO Map PNG** export options record the images:

```
#lightmap arena_lightmap.png
#aomap arena_ao.png
vt u v  u2 v2  u3 v3
```

Faces still index plain `v/vt/vn` — two-float readers get the base UVs.

## Export options

| Option | Default |
|--------|---------|
| Selection Only | off |
| Apply Modifiers | on |
| Triangulate | off |
| Include UVs / Normals / Lights | on |
| Lightmap PNG | (blank = no `#lightmap` line) |
| AO Map PNG | (blank = no `#aomap` line) |
| Color Range | 0..1 floats |
| Forward / Up | −Z / Y |

## Parsing it

Count the floats: `v` has 3 or 6 (position + RGB), `vt` has 2, 4, or 6 (base
UV + lightmap UV + AO UV). The `#` lines are ordinary comments to every other
tool.
Reference consumer: [Affinity](https://github.com/myuu-151/Affinity).

MIT.
