# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# ##### END GPL LICENSE BLOCK #####

# 注意：下面这个 bl_info 字典内不能出现空行。
# Blender 的 addon_utils 在快速模式下只读到 bl_info 之后的第一处空行就停，
# 字典里夹空行会导致它解析到一个未闭合的 "{"，插件会被判定为缺少 bl_info。
bl_info = {
    "name": "Cube Generator",
    "author": "Your Name",
    "version": (1, 1, 1),
    "blender": (4, 2, 0),
    "location": "3D 视图 > 侧边栏(N) > Cube / 添加 > 网格 > 方块",
    "description": "一键生成可定制方块，内置 GitHub 自动更新",
    "category": "Add Mesh",
    # ------------------------------------------------------------------
    # 自动更新配置（只在这里改，addon_updater_ops.py 无需再动）
    # 把下面三处替换成你自己的 GitHub 用户名 / 仓库名 / 主页地址即可。
    # 版本号读的是上面的 "version"，不需要重复填写。
    # ------------------------------------------------------------------
    "updater_user": "xingqifeigao",
    "updater_repo": "fangkuai",
    "updater_website": "https://github.com/xingqifeigao/fangkuai",
    # True = 走 GitHub Releases（需要给每个 Release 附上 zip 附件），
    # False = 走 Tag（自动生成的源码 zip，零额外配置，推荐先用这个）。
    "updater_use_releases": False,
    # 是否允许用户直接从 master 等分支安装（开发期可开）
    "updater_include_branches": False,
    # 是否在控制台打印更新器调试信息
    "updater_verbose": False,
}

import bpy
import bmesh
from mathutils import Vector
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup

from . import addon_updater_ops

# 更新器是否成功注册（失败也不影响方块生成功能）
_updater_ok = False

# 放置位置的三种方式
LOCATION_ITEMS = (
    ("ORIGIN", "世界原点", "方块放置在 (0, 0, 0)"),
    ("CURSOR", "3D 游标", "方块放置在 3D 游标处"),
    ("ACTIVE", "活动物体", "方块放置在当前活动物体的位置"),
)


# -----------------------------------------------------------------------------
# 场景参数：作为面板上的“预设值”，不改动场景
# -----------------------------------------------------------------------------
class CubeGeneratorSettings(PropertyGroup):
    size: FloatProperty(
        name="边长",
        description="方块的边长（米）",
        default=2.0,
        min=0.0001,
        soft_max=20.0,
        precision=3,
        unit="LENGTH",
    )
    subdivisions: IntProperty(
        name="细分",
        description="每条边切分的次数，0 表示不切分",
        default=0,
        min=0,
        max=10,
    )
    smooth: BoolProperty(
        name="平滑着色",
        description="以平滑着色方式显示",
        default=False,
    )
    use_material: BoolProperty(
        name="赋予材质",
        description="为方块新建一个带颜色的材质",
        default=True,
    )
    color: FloatVectorProperty(
        name="颜色",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.85, 0.35, 0.15, 1.0),
    )
    location_mode: EnumProperty(
        name="放置位置",
        description="方块出现的位置",
        items=LOCATION_ITEMS,
        default="CURSOR",
    )
    name_prefix: StringProperty(
        name="名称前缀",
        description="生成物体的名称前缀",
        default="Cube",
    )


# -----------------------------------------------------------------------------
# 核心操作：生成方块
# -----------------------------------------------------------------------------
class CUBE_OT_generate(Operator):
    bl_idname = "mesh.cube_generator_generate"
    bl_label = "生成方块"
    bl_description = "按当前参数生成一个方块"
    bl_options = {"REGISTER", "UNDO"}
    bl_icon = "MESH_CUBE"

    size: FloatProperty(
        name="边长", default=2.0, min=0.0001, soft_max=20.0,
        precision=3, unit="LENGTH",
    )
    subdivisions: IntProperty(name="细分", default=0, min=0, max=10)
    smooth: BoolProperty(name="平滑着色", default=False)
    use_material: BoolProperty(name="赋予材质", default=True)
    color: FloatVectorProperty(
        name="颜色", subtype="COLOR", size=4, min=0.0, max=1.0,
        default=(0.85, 0.35, 0.15, 1.0),
    )
    location_mode: EnumProperty(name="放置位置", items=LOCATION_ITEMS, default="CURSOR")
    name_prefix: StringProperty(name="名称前缀", default="Cube")

    # ---------- 内部工具 ----------
    def _resolve_location(self, context):
        """根据模式返回方块中心的世界坐标"""
        mode = self.location_mode
        if mode == "CURSOR":
            return context.scene.cursor.location.copy()
        if mode == "ACTIVE":
            active = context.view_layer.objects.active
            if active is not None:
                return active.matrix_world.translation.copy()
        return Vector((0.0, 0.0, 0.0))

    def _build_mesh(self, name):
        """用 bmesh 构建立方体网格，边长严格等于 self.size"""
        bm = bmesh.new()
        try:
            bmesh.ops.create_cube(bm, size=1.0)
            if self.subdivisions > 0:
                bmesh.ops.subdivide_edges(
                    bm,
                    edges=list(bm.edges),
                    cuts=self.subdivisions,
                    use_grid_fill=True,
                )
            # 归一化：不同 Blender 版本对 create_cube 的 size 解释有差异，
            # 这里按实际包围盒重新缩放到"边长 = 1"，再乘目标边长。
            coords = [v.co for v in bm.verts]
            if not coords:
                return None
            extent = max(
                max(c.x for c in coords) - min(c.x for c in coords),
                max(c.y for c in coords) - min(c.y for c in coords),
                max(c.z for c in coords) - min(c.z for c in coords),
            )
            if extent <= 0.0:
                return None
            factor = self.size / extent
            bmesh.ops.scale(bm, vec=Vector((factor, factor, factor)), verts=list(bm.verts))

            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            return mesh
        finally:
            bm.free()

    def _make_material(self, name):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        # 视口实体模式的显示色
        mat.diffuse_color = self.color
        node_tree = mat.node_tree
        if node_tree:
            bsdf = node_tree.nodes.get("Principled BSDF")
            if bsdf is not None:
                if "Base Color" in bsdf.inputs:
                    bsdf.inputs["Base Color"].default_value = self.color
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = 0.4
        return mat

    # ---------- 执行 ----------
    def execute(self, context):
        base_name = (self.name_prefix or "Cube").strip() or "Cube"

        mesh = self._build_mesh(base_name)
        if mesh is None:
            self.report({"ERROR"}, "尺寸无效，无法生成方块")
            return {"CANCELLED"}

        if self.smooth:
            mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
        mesh.validate()
        mesh.update()

        if self.use_material:
            mesh.materials.append(self._make_material(base_name + "_Material"))

        obj = bpy.data.objects.new(base_name, mesh)
        obj.location = self._resolve_location(context)

        target_collection = getattr(context, "collection", None) or context.scene.collection
        target_collection.objects.link(obj)

        # 选中并设为活动物体，方便紧接着在 F9 面板里调参数
        try:
            for other in context.view_layer.objects:
                if other.select_get():
                    other.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except (RuntimeError, AttributeError):
            pass

        self.report({"INFO"}, "已生成方块：{}（边长 {}）".format(obj.name, round(self.size, 3)))
        return {"FINISHED"}


# -----------------------------------------------------------------------------
# 侧边栏面板
# -----------------------------------------------------------------------------
class CUBE_PT_main(Panel):
    bl_label = "方块生成器"
    bl_idname = "CUBE_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cube"

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, "cube_gen", None)
        if settings is None:
            layout.label(text="插件未正确初始化", icon="ERROR")
            return

        col = layout.column(align=True)
        col.prop(settings, "size")
        col.prop(settings, "subdivisions")

        row = layout.row(align=True)
        row.prop(settings, "location_mode", text="")
        row.prop(settings, "name_prefix", text="")

        row = layout.row(align=True)
        row.prop(settings, "use_material", text="材质")
        sub = row.row(align=True)
        sub.active = settings.use_material
        sub.prop(settings, "color", text="")
        row.prop(settings, "smooth", text="平滑", toggle=True)

        layout.separator()
        op = layout.operator(CUBE_OT_generate.bl_idname, text="生成方块", icon="MESH_CUBE")
        # 把面板上的预设值传给操作符，F9 重做面板里也能继续调
        op.size = settings.size
        op.subdivisions = settings.subdivisions
        op.smooth = settings.smooth
        op.use_material = settings.use_material
        op.color = settings.color
        op.location_mode = settings.location_mode
        op.name_prefix = settings.name_prefix

        # 有可用更新时，在面板底部显示提示条
        if _updater_ok:
            try:
                addon_updater_ops.update_notice_box_ui(self, context)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# 把更新器的英文报错翻译成能直接照做的中文提示
# -----------------------------------------------------------------------------
def draw_update_hint(layout):
    """根据 updater 的错误内容，在偏好设置里给出可操作的中文说明"""
    updater = addon_updater_ops.updater
    if getattr(updater, "invalid_updater", False):
        return

    err = "{} {}".format(getattr(updater, "error", "") or "",
                         getattr(updater, "error_msg", "") or "")
    err = err.strip()
    if not err:
        return
    low = err.lower()

    box = layout.box()
    col = box.column(align=True)

    if "403" in low or "access denied" in low or "429" in low:
        col.label(text="GitHub 拒绝了这次请求", icon="ERROR")
        col.label(text="短时间请求过多会被限流，或当前代理 IP 被拦。")
        col.label(text="等 10~30 分钟再试。长期方案：配 updater_token。")
    elif "no releases" in low or "no versions" in low:
        col.label(text="仓库里还没有可用的版本标签", icon="INFO")
        col.label(text="去 GitHub 的 Releases 页面发布一个 tag，")
        col.label(text="例如 v1.1.1，然后再点检查更新。")
    elif ("url" in low or "timed out" in low or "resolve" in low
            or "ssl" in low or "connection" in low):
        col.label(text="连不上 GitHub", icon="ERROR")
        col.label(text="检查网络或代理设置后重试。")
    else:
        col.label(text="更新检查未成功", icon="ERROR")
        col.label(text=err[:80])


# -----------------------------------------------------------------------------
# 偏好设置：方块默认值 + 更新器 UI
# -----------------------------------------------------------------------------
class CubeGeneratorPreferences(AddonPreferences):
    bl_idname = __package__

    auto_check_update: BoolProperty(
        name="自动检查更新",
        description="在后台按下方间隔检查 GitHub 上是否有新版本，有则弹窗提示",
        default=False,
    )
    updater_interval_months: IntProperty(name="月", default=0, min=0, soft_max=12)
    updater_interval_days: IntProperty(name="天", default=0, min=0, soft_max=30)
    updater_interval_hours: IntProperty(name="小时", default=6, min=0, soft_max=24)
    updater_interval_minutes: IntProperty(name="分钟", default=0, min=0, soft_max=60)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="方块默认参数", icon="MESH_CUBE")
        settings = getattr(context.scene, "cube_gen", None)
        if settings is not None:
            col = box.column(align=True)
            col.prop(settings, "size")
            col.prop(settings, "subdivisions")
            col.prop(settings, "location_mode")

        layout.separator()
        if _updater_ok:
            addon_updater_ops.update_settings_ui(self, context)
            draw_update_hint(layout)
        else:
            warn = layout.box()
            warn.label(text="更新模块未能加载", icon="ERROR")
            warn.label(text="方块生成功能不受影响")


# -----------------------------------------------------------------------------
# 添加菜单入口
# -----------------------------------------------------------------------------
def draw_mesh_add_menu(self, context):
    self.layout.separator()
    self.layout.operator(
        CUBE_OT_generate.bl_idname,
        text="方块 (Cube Generator)",
        icon="MESH_CUBE",
    )


# -----------------------------------------------------------------------------
# 启动后自动检查一次更新（是否真正联网由偏好设置 + 检查间隔决定）
# -----------------------------------------------------------------------------
def auto_check_timer():
    try:
        if not _updater_ok:
            return None
        addon = bpy.context.preferences.addons.get(__package__, None)
        prefs = getattr(addon, "preferences", None) if addon else None
        if prefs is not None and prefs.auto_check_update:
            addon_updater_ops.check_for_update_background()
    except Exception as exc:  # 更新检查失败绝不影响主功能
        print("[Cube Generator] 自动检查更新跳过：{}".format(exc))
    return None  # 只跑一次


classes = (
    CubeGeneratorSettings,
    CUBE_OT_generate,
    CUBE_PT_main,
    CubeGeneratorPreferences,
)


def register():
    global _updater_ok

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cube_gen = PointerProperty(type=CubeGeneratorSettings)

    # 更新器放在核心功能之后注册，即使它出错也不影响方块生成
    try:
        addon_updater_ops.register(bl_info)
        _updater_ok = not getattr(addon_updater_ops.updater, "invalid_updater", True)
        if not _updater_ok:
            print("[Cube Generator] 更新器初始化异常：{}".format(
                getattr(addon_updater_ops.updater, "error_msg", "unknown")))
    except Exception as exc:
        _updater_ok = False
        print("[Cube Generator] 更新器注册失败（方块功能正常）：{}".format(exc))

    bpy.types.VIEW3D_MT_mesh_add.append(draw_mesh_add_menu)

    if _updater_ok and not bpy.app.background:
        try:
            bpy.app.timers.register(auto_check_timer, first_interval=5.0)
        except Exception as exc:
            print("[Cube Generator] 自动检查定时器启动失败：{}".format(exc))


def unregister():
    global _updater_ok

    if bpy.app.timers.is_registered(auto_check_timer):
        bpy.app.timers.unregister(auto_check_timer)

    try:
        bpy.types.VIEW3D_MT_mesh_add.remove(draw_mesh_add_menu)
    except (ValueError, AttributeError):
        pass

    if _updater_ok:
        try:
            addon_updater_ops.unregister()
        except Exception as exc:
            print("[Cube Generator] 更新器注销异常：{}".format(exc))
    _updater_ok = False

    if hasattr(bpy.types.Scene, "cube_gen"):
        del bpy.types.Scene.cube_gen

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
