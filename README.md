# OBJ 2.0

A Blender add-on that exports Wavefront `.obj` with the things standard OBJ
throws away: **vertex colors**, **Blender lights**, and a second **UV layer**
for lightmaps. Everything stays valid OBJ — importers that don't know the
extensions still read the geometry.

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

## UV layers (lightmaps)

A mesh with a second UV layer (name it `Lightmap`) writes both channels on the
same `vt` line, and the **Lightmap PNG** export option records the image:

```
#lightmap arena_lightmap.png
vt u v u2 v2
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
| Color Range | 0..1 floats |
| Forward / Up | −Z / Y |

## Parsing it

Count the floats: `v` has 3 or 6 (position + RGB), `vt` has 2 or 4 (base UV +
lightmap UV). The `#` lines are ordinary comments to every other tool.
Reference consumer: [Affinity](https://github.com/myuu-151/Affinity).

MIT.
