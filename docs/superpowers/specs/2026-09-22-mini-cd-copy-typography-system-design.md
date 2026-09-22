# Mini CD 文案与字体系统设计

## 目标

在现有“专辑设计”模块中加入可切换的 Copy Layout A/B 与 Typography System。Artwork 永远不生成文字；所有可读文案由程序使用真实字体文件在最终部件上叠加。Mini CD 的物理尺寸、折线、条码、版权和封底曲目逻辑保持不变。

## 边界

- 本期不调用图像模型，也不生成 AI 文案。概念文案由用户输入或由稳定的本地规则提供占位候选。
- 本期的“自动推荐”是确定性规则：只从封面 Visual DNA、主体安全区和现有曲目布局选择预设与字体方向。
- 字体方向不是随机字体选择。程序只能从 Font Library 的真实字体记录中匹配，用户可逐角色替换。
- 仅修改 Mini CD 专辑设计模块。

## 文案数据模型

每个项目新增 `copyLayout`、`typography` 与 `conceptCopy`：

```json
{
  "copyLayout": "auto | editorial | minimal",
  "conceptCopy": {
    "primaryChinese": "",
    "secondaryEnglish": "",
    "shortEnglish": ""
  },
  "typography": {
    "direction": "",
    "display": "auto | font-id",
    "artist": "auto | font-id",
    "chineseCopy": "auto | font-id",
    "englishCopy": "auto | font-id",
    "metadata": "auto | font-id",
    "spine": "auto | font-id"
  }
}
```

空文案表示不渲染该文案，不输出示例句或旧 Golden Reference 的文字。

## Copy Layout A — Editorial / 丰富型

同一 Concept 派生中文主文案、英文概念副文案和可选短英文标签。

| 面板 | 文案角色 | 候选区域 | 对齐与安全规则 |
|---|---|---|---|
| CD Ø40 / 孔 Ø5 | Short English | 外圈的左下或右下 | 避开中心孔、主体和已有标题；仅一条短标签 |
| 41×41 正封面 | Short English | 右上或右下留白 | 不遮挡主体、专辑标题和歌手名 |
| 41×41 内页 | Chinese Primary + English Secondary | 中部或中上留白 | 中文为主，英文在下方；不放生产信息 |
| 49×38 封底 | English Secondary | 曲目区右侧留白 | 不进入曲目、版权、条码固定区域 |
| 49×38 内盘底 | Chinese Primary + English Secondary | 右侧或中部留白 | 中文主文案优先，英文收在底部 |

## Copy Layout B — Minimal / 克制型

保持同一 Concept，但只使用 4–6 个文案落点。

| 面板 | 文案角色 | 候选区域 |
|---|---|---|
| CD | Short English | 左下或右下外圈 |
| 正封面 | Short English | 底部或右上 |
| 内页 | Chinese Primary + English Secondary | 中部留白 |
| 封底 | English Secondary | 左下，避开版权区后使用的安全位置 |
| 左侧封背面 4.4mm | Short English | 竖排或旋转 90° |
| 内盘底 | Chinese Primary + English Secondary | 右下或中部留白 |

## Typography System

所有面板共享一份 Typography System，允许改变字号、方向和位置，不允许每个部件各自随机选字体。

| Role | 用途 | 自动方向 | 程序约束 |
|---|---|---|---|
| Display | 专辑名 | 延续原封面 Serif / Sans / Script / Calligraphy / Display 气质 | 最大层级；真实字体渲染 |
| Artist | 歌手名 | 与 Display 同体系但低一级 | 不抢专辑标题 |
| Chinese Editorial | 中文概念文案 | 轻宋、书写、手写或轻量中文字体 | 不使用默认粗黑体作为编辑文案 |
| English Editorial | 英文概念副文案 | Serif / Sans / Handwriting / Condensed | 次级层级，不逐字翻译中文 |
| Tracklist / Metadata | 曲目、时长、版权、年份 | 清晰稳定的 Functional Typeface | 固定最小可读字号；不可为塞入内容无限缩小 |
| Spine | 4.4mm 侧封 | 窄体、竖排或 90° | 独立排版，不能只缩小 Display |

## Font Library 与授权

Font Library 记录：`id`、`fontFamily`、`path`、`style`、`language`、`weight`、`license`、`commercialStatus`、`usageRoles`。

默认自动匹配只使用 `commercialStatus=verified-open` 的字体。Windows 自带字体可在“本地候选”中手动选择，但必须标为 `license-review-required`，不可作为商业输出默认字体。找不到匹配字体时，使用同角色的 verified-open fallback，并在界面显示实际替代项。

## 自动推荐

`read_design()` 已有调色、明暗、饱和度和风格指标。新增确定性 Typography Direction：

- `minimalist`：优先轻 Serif / 轻量 Sans，默认 Minimal 文案布局。
- `retro`：优先书写感或 Serif Display，封面若存在明显标题字形则优先对应方向。
- `bold`：优先 Display / 几何 Sans，Metadata 仍保持中性 Functional 字体。
- 原封面字形特征可只输出方向标签；本期不承诺 OCR 找到原始字体文件。

自动推荐不得改变用户手动选择。

## 小尺寸印刷规则

- 全部字号根据面板 mm → 输出 DPI 换算，不根据屏幕 CSS 像素决定。
- 曲目、时长和元数据使用明确的最小可读字号。
- 内容过宽时，依次尝试字距、行距、已有单/双列、同角色窄体与文案截短；不降低到最小字号以下。
- 条码、版权、曲目、折线、中心孔和面板边界是 Copy 禁入区。

## UI

在“专辑设计”现有固定模板内容下增加“文案与字体”区域：

1. Copy Layout：自动推荐 / A 丰富型 / B 克制型，带缩略图。
2. Concept Copy：中文主文案、英文副文案、短英文标签，实时预览。
3. Typography Direction：显示自动分析得到的角色方向。
4. Typography：六个角色的 `自动` 与可用字体选择器；显示授权状态。

预览、正式三件套、PNG、PDF、ZIP 和历史任务元数据使用同一份 `copyLayout`、`conceptCopy` 与 `typography`。

## 验收

- A/B 都不改变 40/5、82×41、111.2×38 与 `4.4|49|4.4|4.4|49`。
- A/B 的文案不进入曲目、条码、版权、折线或中心孔禁入区。
- 文案只由程序字体层绘制，Artwork 输入不含文字。
- 英文与中文来自同一 Concept 字段，示例文案绝不写死。
- 手动选择的字体和布局立即更新预览，并在正式输出及历史任务中保持一致。
- 自动匹配仅使用许可明确的默认字体。
