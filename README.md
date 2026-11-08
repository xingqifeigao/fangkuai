# Cube Generator — Blender 方块生成器（含 GitHub 自动更新）

面向 **Blender 4.5 LTS** 的插件：一键生成可定制方块，并集成
[blender-addon-updater](https://github.com/CGCookie/blender-addon-updater) 实现
「检查更新 / 一键安装」的完整发版链路。

已实测环境：Blender **4.5.5 LTS** / Python 3.11.11。

---

## 一、功能

### 1. 生成方块
- **边长**：精确控制，生成结果严格等于设定值
- **细分**：每条边切分 0~10 次
- **平滑着色**：可选
- **材质**：可选，自带 Principled BSDF 颜色
- **放置位置**：世界原点 / 3D 游标 / 活动物体三选一
- **名称前缀**：便于批量管理

两个入口：
- 3D 视图侧边栏 `N` → **Cube** 标签页
- 菜单 `添加 > 网格 > 方块 (Cube Generator)`

生成后按 `F9` 可继续调参数（操作符带 UNDO，标准重做面板）。

### 2. 自动更新
- 读取 GitHub 的 **Releases / Tags**，与 `bl_info["version"]` 做版本比对
- 偏好设置里有「检查更新」按钮，发现新版本可一键下载安装
- 可开启后台定时自动检查，有新版本时弹窗提示
- 更新前自动备份旧版本，支持回滚

---

## 二、安装

1. 偏好设置（`Edit > Preferences`）→ **插件 / Add-ons**
2. 右上角 `⌄` → **从磁盘安装 / Install from Disk...**
3. 选择 `cube_generator_1.0.0.zip`（**不要解压**）
4. 在列表中勾选启用 **Cube Generator**

> ⚠️ 必须用 **zip** 安装。更新器依赖插件以「包（文件夹）」形式存在于
> `scripts/addons/` 下，单文件 `.py` 插件不支持。

---

## 三、配置成你自己的更新源（3 步）

### 第 1 步：改 `__init__.py` 里的 `bl_info`

```python
"updater_user": "你的GitHub用户名",
"updater_repo": "blender-cube-generator",          # 仓库名
"updater_website": "https://github.com/你/blender-cube-generator",
```

只有这一处需要改，`addon_updater_ops.py` 不用动。版本号读的是同一份
`bl_info["version"]`，不需要重复填写。

### 第 2 步：仓库根目录放插件文件

```
blender-cube-generator/          ← 仓库根
├── __init__.py
├── addon_updater.py
├── addon_updater_ops.py
└── README.md
```

即把 `cube_generator/` **里面的内容**放到仓库根目录（不是把 `cube_generator`
文件夹本身放进去）。更新器会自动剥掉 GitHub 源码包多出来的那一层目录。

### 第 3 步：打 tag 发版

```bash
git tag v1.0.1
git push origin v1.0.1
```

- tag 名带不带 `v` 前缀都行（`v1.0.1` / `1.0.1` 都能正确解析）
- 新 tag 的版本号必须 **大于** `bl_info["version"]`，否则不会提示更新
- 发版后记得把 `bl_info["version"]` 也改成新版本号再提交

### 用 Releases 而不是 Tags？

`bl_info` 里设 `"updater_use_releases": True`，此时版本号来源变成 Release
名称，且**必须给每个 Release 附上 zip 附件**，否则拿不到下载链接。零配置起步
建议先用 Tag 模式（默认）。

---

## 四、目录结构

```
cube_generator/
├── __init__.py            # 插件主体：bl_info、操作符、面板、偏好设置
├── addon_updater.py       # 更新引擎（上游 v1.1.1）
├── addon_updater_ops.py   # 更新 UI 与操作符（上游 v1.1.1，已做 4.x 适配）
└── README.md
```

---

## 五、为 Blender 4.5 做的适配改动

上游 `addon_updater` 主分支停留在 2.8x 时代，直接塞进 4.5 能跑但有几处坑。
本包在保持上游 API 完全不变的前提下做了 5 处改动，均以 `[适配改造]` /
`[4.x 适配]` 注释标出：

| 位置 | 改动 | 原因 |
|---|---|---|
| `addon_updater_ops.py` 模块级 | `updater.addon = __package__`（原写死 `"addon_updater_demo"`） | 操作符 `bl_idname` 前缀必须与本插件包名一致，否则注册的 ID 对不上 |
| `register()` 配置段 | `user/repo/website/token` 改为从 `bl_info` 读取 | 仓库地址只需在 `__init__.py` 改一处，避免两份配置漂移 |
| `register()` | `verbose`、`include_branches`、`use_releases` 改为 `bl_info` 驱动，默认关闭 | 面向正式发版，减少控制台噪音和多余按钮 |
| 两个 `@persistent` handler | 签名改为 `(scene, depsgraph=None)` | 它们被挂到 `depsgraph_update_post`；4.x 会传两个参数，双签名两种都兼容 |
| `__init__.py` | 更新器注册包裹 `try/except`，失败只降级不影响方块功能 | 断网、代理异常时插件主功能仍可用 |

`addon_updater.py` 未做任何逻辑改动。

---

## 六、实测结果

在 Blender 4.5.5 LTS 后台模式下跑通了完整链路：

- 插件启用 / 注销 / 反复重载：**35 项检查全部通过**
- 方块几何：边长精度 1e-5、顶点面数、细分、平滑、材质、三种放置模式均正确
- UI：侧边栏面板、偏好设置面板、「检查更新」按钮、添加菜单、更新提示条均可正常绘制
- 更新链路（指向真实公开仓库）：拉取 tag → 版本比对 `(1,0,0) < v1.1.1` →
  返回 `update_ready=True` → 下载 zip → 解压 → 备份 → 覆盖文件 →
  写入 `just_updated` 标记 → 提示「Restart blender to reload addon and complete update」
- 异步后台检查（自动检查走的就是这条路径）回调正常返回

---

## 七、注意事项

- 更新完成后需 **重启 Blender** 才会加载新代码（`auto_reload_post_update=False`，
  这是官方推荐设置，会话内热重载容易崩）
- 私有仓库需要在 `bl_info` 里配 `updater_token`，注意 token 会随插件分发
- 开发机上不要直接点「更新」，会覆盖你本地正在改的代码；先把改动提交
- GitHub 匿名 API 有 60 次/小时限流，正常使用完全够
- 插件目录内会生成 `cube_generator_updater/` 暂存与备份文件夹，属正常现象
