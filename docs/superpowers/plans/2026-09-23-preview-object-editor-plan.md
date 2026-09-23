# 预览对象点选编辑器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在迷你 CD 实时预览中点选文字对象，并通过统一格式栏直接修改该对象的字体、字号、粗斜体与颜色，且最终成品与预览使用一致格式。

**Architecture:** 在现有 `copy_settings` 中新增统一的 `textAppearance` 映射，键为 `title`、`artist`、`chineseCopy`、`englishCopy`、`metadata`、`spineRight`、`spineLeft`、`spineLeftBack`。后端在规范化设置时兼容现有 `spineAppearance`，渲染时从统一映射读取；前端维护当前选中对象，使用预览上的可访问透明命中区域驱动唯一的格式栏。

**Tech Stack:** Python、Pillow、标准库 `unittest`、静态 HTML/CSS/JavaScript、本地 HTTP 服务。

**Spec:** `docs/superpowers/specs/2026-09-23-preview-object-editor-design.md`

## Global Constraints

- 文字位置继续由模板和安全区控制，本轮不提供自由拖动或缩放。
- 侧封的字号继续使用毫米，并受真实 4.4×38 mm 安全区限制。
- 预览和最终 PNG 必须传递同一份对象格式数据。
- 保持旧项目 `spineAppearance` 数据可读取。
- 不添加新的前端依赖；临时截图与浏览器缓存不能提交。

## Review Focus

- 旧项目只含 `spineAppearance` 时，三个侧封必须保持原有字体、字号、样式和颜色；在任务 1 增加迁移测试。
- 默认“标题＋歌手”模板没有手动文本时，选择的颜色、字体与样式仍必须进入 PNG；在任务 2 增加像素颜色测试。
- 用户选中不同侧封后，统一格式栏必须读取该条侧封独立状态；在任务 3 增加 DOM 状态测试。
- 用户点击非文字区域或没有生成结果时，工具栏不得报错且保留上次合法选择；在任务 3 增加浏览器交互验证。
- 小屏和窄工具栏下，命中区域和格式栏不得遮挡 4.4×38 mm 预览；在任务 4 进行桌面与移动视口截图检查。

---

### Task 1: 统一对象格式的数据契约

**Files:**
- Modify: `tools/copy_typography.py:1-56`
- Modify: `tests/test_copy_typography.py`

**Interfaces:**
- Consumes: 前端请求中的 `textAppearance: dict[str, dict]` 与旧 `spineAppearance: dict[str, dict]`。
- Produces: `normalize_copy_settings(raw) -> dict`，其中 `textAppearance` 包含八个对象键；`spineAppearance` 继续由三个侧封键派生以供旧调用方读取。

- [ ] **Step 1: 写入失败测试，定义默认值、合法格式与旧数据迁移。**

```python
def test_text_appearance_migrates_old_spine_settings():
    from copy_typography import normalize_copy_settings
    result = normalize_copy_settings({"spineAppearance": {"right": {
        "font": "noto-sans-sc", "sizeMm": 2.2,
        "style": "bold", "color": "#C8102E"}}})
    right = result["textAppearance"]["spineRight"]
    self.assertEqual(right["font"], "noto-sans-sc")
    self.assertEqual(right["sizeMm"], 2.2)
    self.assertEqual(right["color"], "#c8102e")
    self.assertEqual(result["spineAppearance"]["right"], right)
```

- [ ] **Step 2: 运行测试，确认当前实现失败。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_copy_typography.CopyTypographyTests.test_text_appearance_migrates_old_spine_settings -v`

Expected: FAIL，因为 `textAppearance` 尚不存在。

- [ ] **Step 3: 实现规范化与兼容映射。**

```python
TEXT_OBJECTS = ("title", "artist", "chineseCopy", "englishCopy", "metadata",
                "spineRight", "spineLeft", "spineLeftBack")
SPINE_OBJECT_TO_ZONE = {"spineRight": "right", "spineLeft": "left", "spineLeftBack": "leftBack"}

def _text_appearance(raw, *, spine=False):
    # font、style、color 与现有 _spine_appearance 使用相同验证；
    # 普通对象使用 pt 字号，侧封使用 0.8–2.6 mm。
    ...
```

在 `normalize_copy_settings` 中，先从 `textAppearance` 读取；缺失侧封对象时以旧 `spineAppearance` 补齐，再生成兼容的 `spineAppearance` 返回值。

- [ ] **Step 4: 运行对象格式与既有字体测试。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_copy_typography tests.test_font_library -v`

Expected: PASS。

- [ ] **Step 5: 提交数据契约。**

```powershell
git add tools/copy_typography.py tests/test_copy_typography.py
git commit -m "feat: normalize object text appearances"
```

### Task 2: 让最终成品按对象格式绘制

**Files:**
- Modify: `tools/design_parts.py:1727-1927`
- Modify: `tools/make_minicd.py`
- Modify: `tests/test_copy_typography.py`

**Interfaces:**
- Consumes: `copy_settings["textAppearance"]`，包含任务 1 的八个对象设置。
- Produces: `spine_overlay(...)` 对固定模板和手动文字应用 `spineRight`、`spineLeft`、`spineLeftBack`；封面、背面、信息区绘制函数读取其对应对象样式。

- [ ] **Step 1: 写入失败测试，证明固定侧封模板与普通标题使用对象颜色。**

```python
def test_fixed_template_and_title_use_object_color():
    from PIL import Image
    from design_parts import spine_overlay
    strip = Image.new("RGB", (88, 760), "white")
    result = spine_overlay(strip, "right", "ALBUM", "ARTIST", copy_settings={
        "textAppearance": {"spineRight": {"font": "auto", "sizeMm": 1.7,
                                             "style": "normal", "color": "#2563eb"}}})
    self.assertTrue(any(b > 130 and r < 100 for r, g, b in result.getdata()))
```

另为标题绘制入口添加一个同色断言，确保 `title` 不是只存在于请求数据中。

- [ ] **Step 2: 运行测试，确认普通对象格式当前尚未进入对应绘制路径。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_copy_typography.CopyTypographyTests.test_fixed_template_and_title_use_object_color -v`

Expected: FAIL，或标题断言失败。

- [ ] **Step 3: 在渲染边界集中读取对象外观。**

```python
def text_appearance(copy_settings, object_id, automatic_fill):
    appearance = ((copy_settings or {}).get("textAppearance") or {}).get(object_id) or {}
    return {
        "font": appearance.get("font", "auto"),
        "fill": _spine_fill(appearance.get("color"), automatic_fill),
        "style": appearance.get("style", "normal"),
        "size": appearance.get("sizePt"),
        "sizeMm": appearance.get("sizeMm"),
    }
```

使用该函数替换各文字绘制点的硬编码字体与颜色；对侧封维持毫米换算、纵排与安全高度截断。不要改变任何对象的模板位置。

- [ ] **Step 4: 运行生成相关测试。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_copy_typography tests.test_title_compositor -v`

Expected: PASS。

- [ ] **Step 5: 提交最终绘制支持。**

```powershell
git add tools/design_parts.py tools/make_minicd.py tests/test_copy_typography.py
git commit -m "feat: apply object text styles to artwork"
```

### Task 3: 预览点选与统一格式栏

**Files:**
- Modify: `workbench/design.html:35-37, 384-398, 550-670`
- Modify: `tests/test_design_ui_regression.py`

**Interfaces:**
- Consumes: `TEXT_OBJECTS` 同名对象 ID、`currentCopySettings()` 的 `textAppearance`。
- Produces: `TEXT_EDITOR_OBJECT`、`setTextEditorObject(id)`、`syncTextFormatToolbar()`、`textAppearance` 请求字段，以及标有 `data-text-object` 的预览命中区域。

- [ ] **Step 1: 写入静态回归测试，锁定唯一格式栏和所有对象命中区。**

```python
def test_preview_object_editor_has_one_toolbar_and_all_targets(self):
    html = (ROOT / "workbench" / "design.html").read_text(encoding="utf-8")
    self.assertIn('id="textFormatToolbar"', html)
    for object_id in ("title", "artist", "chineseCopy", "englishCopy", "metadata",
                      "spineRight", "spineLeft", "spineLeftBack"):
        self.assertIn(f'data-text-object="{object_id}"', html)
    self.assertIn("function setTextEditorObject", html)
    self.assertIn("textAppearance:TEXT_APPEARANCE", html)
```

- [ ] **Step 2: 运行测试，确认当前角色型字体页与侧封专属工具栏不能满足要求。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_design_ui_regression.DesignUiRegressionTests.test_preview_object_editor_has_one_toolbar_and_all_targets -v`

Expected: FAIL。

- [ ] **Step 3: 实现统一状态和工具栏。**

```javascript
const TEXT_OBJECTS = ['title','artist','chineseCopy','englishCopy','metadata',
  'spineRight','spineLeft','spineLeftBack'];
let TEXT_EDITOR_OBJECT = 'title';
let TEXT_APPEARANCE = Object.fromEntries(TEXT_OBJECTS.map(id => [id, defaultTextAppearance(id)]));
function setTextEditorObject(id) {
  if (!TEXT_APPEARANCE[id]) return;
  TEXT_EDITOR_OBJECT = id;
  syncTextFormatToolbar();
  renderPreviewSelection();
}
```

删除按角色显示的字体选择网格，替换为一个带字体、字号、粗体、斜体、颜色的 `#textFormatToolbar`。保留字体库数据与所有自定义颜色逻辑；将侧封标签切换映射为 `spineRight`、`spineLeft`、`spineLeftBack`，不再维护第二套侧封格式栏。

- [ ] **Step 4: 为预览增加命中区域和状态同步。**

在每个预览部件的容器内放置带 `data-text-object` 的绝对定位按钮；命中区域仅用于选择，不遮挡图片下载、放大或其他控件。每次 `queuePreview()` 成功更新图片后重新应用选中框。单击命中区调用 `setTextEditorObject`，格式栏每次修改都更新 `TEXT_APPEARANCE[TEXT_EDITOR_OBJECT]` 并调用 `queuePreview()`。

- [ ] **Step 5: 运行页面回归测试。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_design_ui_regression -v`

Expected: PASS。

- [ ] **Step 6: 提交统一编辑界面。**

```powershell
git add workbench/design.html tests/test_design_ui_regression.py
git commit -m "feat: edit preview text with one toolbar"
```

### Task 4: 端到端预览与生成核验

**Files:**
- Modify: `tests/test_design_ui_regression.py`
- Modify: `workbench/server.py`（仅在请求契约需要显式透传时）

**Interfaces:**
- Consumes: 任务 1–3 的 `textAppearance` 请求数据。
- Produces: `/api/design/preview` 与 `/api/design/build` 一致透传并保存对象格式。

- [ ] **Step 1: 写入请求数据回归测试。**

```python
def test_preview_and_build_keep_text_appearance(self):
    # 使用现有服务测试辅助函数提交 title 和 spineRight 的不同颜色；
    # 读取保存 state，断言两个对象的颜色均未被自动色覆盖。
    ...
```

- [ ] **Step 2: 运行测试，确认请求或保存路径缺少该字段时失败。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_design_ui_regression -v`

Expected: FAIL，直到服务状态可回读 `textAppearance`。

- [ ] **Step 3: 补齐服务透传与状态保存。**

确保 `workbench/design_service.py`、`workbench/server.py` 的 preview、build、state 路径均使用任务 1 的规范化结果；不得在 build 时重新创建默认格式覆盖用户已选对象格式。

- [ ] **Step 4: 运行完整回归套件。**

Run: `C:\Users\CH\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\python.exe -m unittest tests.test_font_library tests.test_copy_typography tests.test_design_ui_regression tests.test_title_compositor -v`

Expected: PASS。

- [ ] **Step 5: 做浏览器视觉核验。**

The flow under test is: `http://127.0.0.1:8765/design` → 点击标题、歌手和右侧封命中区 → 修改颜色与字体 → 实时预览更新 → 生成成品。

使用本地 Chrome DevTools 或可用 Browser 工具核验：页面非空、无控制台错误、桌面截图和 390 px 宽截图均可见统一格式栏；选中右侧封后显示毫米字号，选中标题后显示普通字号；生成图中对象颜色与预览一致。

- [ ] **Step 6: 提交端到端支持。**

```powershell
git add workbench/server.py workbench/design_service.py tests/test_design_ui_regression.py
git commit -m "feat: preserve object styles through preview and build"
```
