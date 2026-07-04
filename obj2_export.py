# OBJ 2.0 — Wavefront .obj exporter that keeps vertex colors.
#
# Standard Wavefront OBJ has no way to store vertex colors. The de-facto
# extension (used by MeshLab, Blender's own importer, and others) simply
# appends the color to the vertex line:
#
#     v  x y z  r g b
#
# This add-on writes exactly that — ordinary OBJ geometry (v / vt / vn / f)
# plus per-vertex RGB on every `v` line — so importers that don't understand
# the extra columns still read the geometry, while importers that do (e.g.
# the Affinity engine) pick up the colors.
#
# It can also carry the scene's LIGHTING RIG as comment lines (still 100%
# valid OBJ — every other importer skips them):
#
#     #ambient r g b                       (world color * strength)
#     #light   x y z  r g b  energy radius (point light; radius = custom
#                                           distance cutoff, 0 = none)
#     #sun     dx dy dz  r g b  strength   (sun; direction the light travels)
#
# Positions/directions go through the same Forward/Up axis conversion as the
# geometry, so a consuming engine can light the model exactly as authored.
#
# Install: Blender > Edit > Preferences > Add-ons > Install… > pick this file >
# enable "OBJ 2.0 — Wavefront export with vertex colors".
# Use:     File > Export > OBJ 2.0 — Wavefront + Vertex Colors (.obj)
#
# Tested against Blender 4.x.

bl_info = {
    "name": "OBJ 2.0 — Wavefront export with vertex colors",
    "author": "myuu-151",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "File > Export > OBJ 2.0 (.obj)",
    "description": "Export Wavefront .obj with per-vertex colors (v x y z r g b) and the scene light rig (#light/#sun/#ambient).",
    "category": "Import-Export",
}

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, axis_conversion
from mathutils import Vector


def _loop_normal_getter(me):
    """Return a function loop_index -> normal vector, across Blender versions."""
    try:
        cn = me.corner_normals          # Blender 4.1+
        return lambda li: cn[li].vector
    except Exception:
        try:
            me.calc_normals_split()     # Blender <= 4.0
        except Exception:
            pass
        return lambda li: me.loops[li].normal


def _vertex_color_getter(me):
    """Return a function vertex_index -> (r, g, b) in 0..1, or None if no colors.

    Handles both POINT (per-vertex) and CORNER (per-face-corner) color
    attributes; CORNER colors are averaged down to one color per vertex.
    """
    ca = me.color_attributes
    if not ca:
        return None
    layer = ca.active_color or ca[0]
    data = layer.data

    if layer.domain == 'POINT':
        def get(vi):
            c = data[vi].color
            return (c[0], c[1], c[2])
        return get

    # CORNER: average the loop colors that touch each vertex.
    acc = [[0.0, 0.0, 0.0, 0] for _ in range(len(me.vertices))]
    for li, loop in enumerate(me.loops):
        c = data[li].color
        a = acc[loop.vertex_index]
        a[0] += c[0]; a[1] += c[1]; a[2] += c[2]; a[3] += 1

    def get(vi):
        a = acc[vi]
        n = a[3] if a[3] else 1
        return (a[0] / n, a[1] / n, a[2] / n)
    return get


def _world_ambient(scene):
    """World background color * strength -> flat ambient term, in 0..n."""
    w = scene.world
    if not w:
        return (0.05, 0.05, 0.05)
    if w.use_nodes and w.node_tree:
        for n in w.node_tree.nodes:
            if n.type == 'BACKGROUND':
                c = n.inputs['Color'].default_value
                s = n.inputs['Strength'].default_value
                return (c[0] * s, c[1] * s, c[2] * s)
    c = w.color
    return (c[0], c[1], c[2])


class ExportOBJ2(bpy.types.Operator, ExportHelper):
    """Export Wavefront .obj with per-vertex colors (v x y z r g b)"""
    bl_idname = "export_scene.obj2"
    bl_label = "Export OBJ 2.0"
    filename_ext = ".obj"
    filter_glob: StringProperty(default="*.obj", options={'HIDDEN'})

    use_selection: BoolProperty(
        name="Selection Only", default=False,
        description="Export only selected objects")
    apply_modifiers: BoolProperty(
        name="Apply Modifiers", default=True,
        description="Export the modifier-evaluated mesh")
    triangulate: BoolProperty(
        name="Triangulate", default=False,
        description="Triangulate n-gons / quads on export")
    write_uvs: BoolProperty(name="Include UVs", default=True)
    write_normals: BoolProperty(name="Include Normals", default=True)
    write_lights: BoolProperty(
        name="Include Lights", default=True,
        description="Write point/sun lights and world ambient as #light/#sun/#ambient "
                    "comment lines (read by the Affinity engine, ignored by other importers)")
    color_scale: EnumProperty(
        name="Color Range",
        items=[('UNIT', "0..1 floats", "MeshLab / Blender convention (recommended)"),
               ('BYTE', "0..255 ints", "Some engines expect 0-255")],
        default='UNIT')
    forward_axis: EnumProperty(
        name="Forward",
        items=[(a, a, "") for a in ('X', 'Y', 'Z', '-X', '-Y', '-Z')],
        default='-Z')
    up_axis: EnumProperty(
        name="Up",
        items=[(a, a, "") for a in ('X', 'Y', 'Z', '-X', '-Y', '-Z')],
        default='Y')

    def execute(self, context):
        return _write_obj2(self, context)


def _write_obj2(op, context):
    depsgraph = context.evaluated_depsgraph_get()
    global_matrix = axis_conversion(to_forward=op.forward_axis,
                                    to_up=op.up_axis).to_4x4()

    source = context.selected_objects if op.use_selection else context.scene.objects
    mesh_objs = [o for o in source if o.type == 'MESH']
    if not mesh_objs:
        op.report({'ERROR'}, "No mesh objects to export")
        return {'CANCELLED'}

    with open(op.filepath, 'w', encoding='utf-8') as f:
        f.write("# OBJ 2.0 — Wavefront OBJ with per-vertex colors\n")
        f.write("# vertex lines carry color: v x y z r g b\n")

        # --- Lighting rig (comment lines: valid OBJ for every importer) ---
        if op.write_lights:
            lamps = [o for o in source
                     if o.type == 'LIGHT' and o.data.type in {'POINT', 'SUN'}]
            if lamps:
                amb = _world_ambient(context.scene)
                f.write("# lighting rig: #ambient r g b | #light x y z r g b energy radius | #sun dx dy dz r g b strength\n")
                f.write("#ambient %.4f %.4f %.4f\n" % (amb[0], amb[1], amb[2]))
                for o in lamps:
                    d = o.data
                    c = d.color
                    if d.type == 'POINT':
                        loc = global_matrix @ o.matrix_world.translation
                        radius = d.cutoff_distance if d.use_custom_distance else 0.0
                        f.write("#light %.4f %.4f %.4f %.4f %.4f %.4f %.2f %.2f\n"
                                % (loc.x, loc.y, loc.z, c[0], c[1], c[2], d.energy, radius))
                    else:  # SUN — Blender lights aim down their local -Z
                        dv = (global_matrix.to_3x3()
                              @ (o.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0)))).normalized()
                        f.write("#sun %.4f %.4f %.4f %.4f %.4f %.4f %.3f\n"
                                % (dv.x, dv.y, dv.z, c[0], c[1], c[2], d.energy))

        v_off = vt_off = vn_off = 0
        for obj in mesh_objs:
            eval_obj = obj.evaluated_get(depsgraph) if op.apply_modifiers else obj
            me = eval_obj.to_mesh()
            if me is None:
                continue
            try:
                if op.triangulate:
                    import bmesh
                    bm = bmesh.new()
                    bm.from_mesh(me)
                    bmesh.ops.triangulate(bm, faces=bm.faces)
                    bm.to_mesh(me)
                    bm.free()

                mat = global_matrix @ obj.matrix_world
                mat_n = mat.to_3x3().inverted_safe().transposed()
                get_col = _vertex_color_getter(me)
                get_nrm = _loop_normal_getter(me) if op.write_normals else None

                f.write("o %s\n" % obj.name)

                # --- Vertices (+ color) ---
                for v in me.vertices:
                    co = mat @ v.co
                    if get_col:
                        r, g, b = get_col(v.index)
                        if op.color_scale == 'BYTE':
                            f.write("v %.6f %.6f %.6f %d %d %d\n" % (
                                co.x, co.y, co.z,
                                max(0, min(255, round(r * 255))),
                                max(0, min(255, round(g * 255))),
                                max(0, min(255, round(b * 255)))))
                        else:
                            f.write("v %.6f %.6f %.6f %.6f %.6f %.6f\n" % (
                                co.x, co.y, co.z, r, g, b))
                    else:
                        f.write("v %.6f %.6f %.6f\n" % (co.x, co.y, co.z))

                # --- UVs (per loop, deduplicated) ---
                uv_layer = me.uv_layers.active.data if (op.write_uvs and me.uv_layers.active) else None
                loop_uv = [0] * len(me.loops)
                uv_list = []
                if uv_layer:
                    uv_index = {}
                    for li in range(len(me.loops)):
                        uv = uv_layer[li].uv
                        key = (round(uv.x, 6), round(uv.y, 6))
                        idx = uv_index.get(key)
                        if idx is None:
                            idx = len(uv_list)
                            uv_index[key] = idx
                            uv_list.append(key)
                        loop_uv[li] = idx
                    for u, w in uv_list:
                        f.write("vt %.6f %.6f\n" % (u, w))

                # --- Normals (per loop, deduplicated) ---
                loop_nrm = [0] * len(me.loops)
                nrm_list = []
                if get_nrm:
                    nrm_index = {}
                    for li in range(len(me.loops)):
                        nv = (mat_n @ get_nrm(li)).normalized()
                        key = (round(nv.x, 5), round(nv.y, 5), round(nv.z, 5))
                        idx = nrm_index.get(key)
                        if idx is None:
                            idx = len(nrm_list)
                            nrm_index[key] = idx
                            nrm_list.append(key)
                        loop_nrm[li] = idx
                    for nx, ny, nz in nrm_list:
                        f.write("vn %.6f %.6f %.6f\n" % (nx, ny, nz))

                # --- Faces ---
                for poly in me.polygons:
                    f.write("f")
                    for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                        vi = me.loops[li].vertex_index + 1 + v_off
                        if uv_layer and get_nrm:
                            f.write(" %d/%d/%d" % (vi, loop_uv[li] + 1 + vt_off, loop_nrm[li] + 1 + vn_off))
                        elif uv_layer:
                            f.write(" %d/%d" % (vi, loop_uv[li] + 1 + vt_off))
                        elif get_nrm:
                            f.write(" %d//%d" % (vi, loop_nrm[li] + 1 + vn_off))
                        else:
                            f.write(" %d" % vi)
                    f.write("\n")

                v_off += len(me.vertices)
                vt_off += len(uv_list)
                vn_off += len(nrm_list)
            finally:
                eval_obj.to_mesh_clear()

    op.report({'INFO'}, "Exported OBJ 2.0: %s" % op.filepath)
    return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(ExportOBJ2.bl_idname,
                         text="OBJ 2.0 — Wavefront + Vertex Colors (.obj)")


def register():
    bpy.utils.register_class(ExportOBJ2)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ExportOBJ2)


if __name__ == "__main__":
    register()
