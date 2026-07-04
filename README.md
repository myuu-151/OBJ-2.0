# OBJ 2.0

A tiny Blender add-on that exports **Wavefront `.obj` with vertex colors**
— and, since 1.1, **the scene's lighting rig**.

Standard OBJ throws vertex colors away. OBJ 2.0 keeps them using the common
extended-vertex convention — the color is appended to each vertex line:

```
v  x y z  r g b
```

Point/sun lights and the world ambient ride along as comment lines:

```
#ambient r g b
#light   x y z  r g b  energy radius
#sun     dx dy dz  r g b  strength
```

Geometry stays 100% valid OBJ (`v` / `vt` / `vn` / `f`, comments for the
lights), so importers that ignore the extras still load the mesh, while
importers that understand them (e.g. the
[Affinity](https://github.com/myuu-151/Affinity) engine) pick up the
per-vertex color and light the model exactly as authored in Blender.

## Install

1. Download `obj2_export.py`.
2. Blender → **Edit → Preferences → Add-ons → Install…** → select the file.
3. Tick **OBJ 2.0 — Wavefront export with vertex colors** to enable it.

## Export

**File → Export → OBJ 2.0 — Wavefront + Vertex Colors (.obj)**

Options:

| Option | Default | Notes |
|--------|---------|-------|
| Selection Only | off | Export only selected objects |
| Apply Modifiers | on | Export the modifier-evaluated mesh |
| Triangulate | off | Split quads / n-gons into triangles |
| Include UVs / Normals | on | Write `vt` / `vn` and `f v/vt/vn` |
| Include Lights | on | Write `#light` / `#sun` / `#ambient` lines |
| Color Range | `0..1 floats` | or `0..255 ints` |
| Forward / Up | `-Z` / `Y` | Matches Blender's default OBJ axis conversion |

The active **Color Attribute** is used. Both `POINT` (per-vertex) and `CORNER`
(per-face-corner) domains work — corner colors are averaged to one color per
vertex. If the mesh has no color attribute, plain `v x y z` lines are written.

## File format

A normal OBJ, except `v` lines have three extra numbers — red, green, blue —
and the light rig sits at the top as comment lines:

```
# OBJ 2.0 — Wavefront OBJ with per-vertex colors
# vertex lines carry color: v x y z r g b
#ambient 0.0509 0.0509 0.0509
#light 4.0762 5.9039 -1.0055 1.0000 0.9500 0.8000 1000.00 0.00
#sun -0.3011 -0.7011 0.6462 1.0000 1.0000 1.0000 3.000
o Cube
v -1.000000 -1.000000 1.000000 0.901961 0.215686 0.184314
v -1.000000  1.000000 1.000000 0.180392 0.760784 0.298039
...
vt 0.000000 0.000000
vn 0.000000 0.000000 1.000000
f 1/1/1 2/2/1 3/3/1
```

- Colors default to **0..1 floats** (MeshLab / Blender convention). Switch the
  export option to **0..255 ints** if your importer expects bytes.
- A vertex with no color (mesh without a color attribute) is written as the
  usual `v x y z` — so you can mix colored and uncolored meshes.

### Light lines

| Line | Fields | Notes |
|------|--------|-------|
| `#ambient r g b` | world background color × strength | written once |
| `#light x y z r g b energy radius` | position, color, watts, cutoff | point light; `radius` is Blender's *Custom Distance* (0 = none) |
| `#sun dx dy dz r g b strength` | travel direction, color, W/m² | direction is where the light *goes* (Blender lights aim −Z) |

Positions and directions go through the same **Forward / Up** axis conversion
as the geometry. Only `POINT` and `SUN` lamps are exported; with *Selection
Only* enabled, only selected lamps are considered. A Blender-matched diffuse
response for consumers: point ≈ `E·max(0,N·L)/(4π²·d²)`, sun ≈ `strength/π·max(0,N·L)`.

## Parsing it

The color columns are optional, so a parser just reads however many floats
follow `v`:

```c
// returns vertex count fields parsed from a "v ..." line
float x, y, z, r = 1, g = 1, b = 1;
int n = sscanf(line, "v %f %f %f %f %f %f", &x, &y, &z, &r, &g, &b);
// n == 3  -> position only (no color, default white)
// n == 6  -> position + RGB
```

## License

MIT.
