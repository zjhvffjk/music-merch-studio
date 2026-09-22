# AI Artistic Typography 设计规格

## 目标

在现有 Mini CD 专辑设计工作台中增加“AI 艺术字 / Title Lettering”模块。系统先从原封面和 Visual DNA 推导标题字方向，然后生成、选择并保存一个独立的标题艺术字资产，跨盘面、封面、封面背面、封底、侧封与内盘底复用。曲目、时长、版权、条码永远使用功能字体。

## 已确认约束

- 参考产品只用于效果与交互参考，不调用或爬取其服务：Adobe Express、ArtFont、Canva、标智客。
- 当前阶段不接第三方付费 API，不得把普通字体旋转伪装成 AI 艺术字。
- Artwork、Title Lettering、Concept Copy、Tracklist/Metadata、Barcode 必须分层。
- 标题资产优先为透明 PNG；可用 SVG 时一并保存原始 SVG。
- 同一个选定标题资产必须在整套 Mini CD 复用，不能每个面重新生成。
- 几何模板固定：盘面 Ø40 / 孔 Ø5；折件 82×41；盒体展开 111.2×38，分段 4.4+49+4.4+4.4+49 mm。
- 标题艺术字只能进入各部件安全区；不得覆盖中心孔、曲目、版权、条码、折线、裁切线或已识别主体。

## 三种标题模式

1. `cover-follow`：默认。基于原封面标题特征生成 Typography Direction；没有已选资产时，使用现有真实字体标题作为稳定回退。
2. `font`：用户选择可商用字体库中的字体，并按真实字体渲染。
3. `artistic`：使用一个已选择的 `TitleLetteringAsset`。用户可上传透明 PNG/SVG、选候选或回退到字体模式。

## 数据模型

```json
{
  "titleMode": "cover-follow | font | artistic",
  "titleDirection": {
    "category": "brush-calligraphy | handwritten | editorial-serif | geometric-sans | retro-display | experimental",
    "weight": "light | regular | bold",
    "tracking": "tight | normal | wide",
    "slantDeg": 3,
    "palette": ["#1f1b18"],
    "referenceSource": "cover-title-region | user-upload | manual"
  },
  "titleCandidates": [
    {
      "id": "ttl_xxx_01",
      "provider": "local-upload | provider-id",
      "status": "ready | failed | pending",
      "assetPng": "assets/title/ttl_xxx_01.png",
      "assetSvg": null,
      "prompt": "...",
      "direction": {"category": "brush-calligraphy", "slantDeg": 3}
    }
  ],
  "selectedTitleAssetId": "ttl_xxx_01"
}
```

## 原封面标题参考提取

Visual DNA 阶段新增可选的 `CoverTitleReferenceExtraction`，用于让艺术字生成参考原封面真实标题的字形气质，而不只依赖“手写/衬线”等文字标签。

```json
{
  "coverTitleReference": {
    "status": "detected | unavailable | rejected",
    "sourceImage": "cover.jpg",
    "cropPng": "assets/title-references/ref_xxx.png",
    "titleBBox": {"x": 0.12, "y": 0.18, "width": 0.42, "height": 0.16},
    "confidence": 0.86,
    "titleStyleDescription": "黑色手写行书，笔触粗细变化，基线向右上轻扬",
    "titleDirection": {"category": "brush-calligraphy", "slantDeg": 3}
  }
}
```

提取规则：仅在标题区域检测置信度达到阈值、区域不包含人物脸部或大面积摄影主体、且裁切尺寸足以辨认标题风格时保存。否则状态为 `unavailable` 或 `rejected`，艺术字生成只使用 Visual DNA 和 Typography Direction；禁止凭猜测裁切错误画面。

## 四个候选的受控差异

每一次生成固定要求四个属于同一张专辑 Visual DNA 的候选，而不是同一 prompt 的四次随机采样：

1. `closest-original`：最接近 `coverTitleReference` 的标题字形、颜色、笔触和倾斜。
2. `editorial`：保留原始气质，增强高级唱片/杂志标题的秩序、留白和可读性。
3. `expressive`：强化笔触、形态、材质或视觉表现，但仍保持标题可辨认。
4. `minimal`：最克制的单色或低材质版本，优先保证 Mini CD 小尺寸印刷可读性。

每个 candidate 必须携带 `variant`、独立 prompt、方向说明、透明背景状态及可印刷尺寸。用户选中的一个才成为唯一 `selectedTitleAssetId`。

## Provider 契约

```python
class ArtisticTypographyProvider(Protocol):
    provider_id: str
    def generate(self, request: ArtisticTypographyRequest) -> list[TitleLetteringCandidate]: ...

@dataclass
class ArtisticTypographyRequest:
    album: str
    artist: str
    language: str
    visual_dna: dict
    title_direction: dict
    reference_image: str | None
    count: int = 4

@dataclass
class TitleLetteringCandidate:
    id: str
    provider: str
    png_path: str | None
    svg_path: str | None
    width: int
    height: int
    transparent: bool
    prompt: str
    title_direction: dict
```

### Phase 1：资产与排版基础设施

实现 `ManualAssetProvider`（上传 PNG/SVG）与 `UnavailableProvider`（明确返回“尚未配置 AI Provider”，不制造假候选）、四候选 UI、标题资产复用、Compositor 和 Print Ready 集成。

### Phase 2：真实 AI Artistic Typography Provider

最终“自动生成”必须调用已配置的真实 Provider，执行：

`Visual DNA → Typography Direction → Artistic Typography Prompt → AI Provider → 4 个透明背景候选 → Candidate Assets → 用户选择 → 全套复用`

Phase 2 的 Provider 接入不得改动 UI、候选数据模型、资产存储、Mini CD compositor 或任何物理规格；只新增 Provider 实现与凭据配置。Provider 应优先请求透明 PNG；若只返回不透明图，必须先经背景移除和人工可见边界校验，不能直接作为生产标题资产。

## 版面复用规则

`TitleAssetPlacement` 以毫米坐标记录每个面的位置、最大安全宽高、对齐和旋转。艺术字源文件只保存一份；各面只引用同一 asset id 与不同 placement。

- 盘面：避开 Ø5mm 中心孔，默认上半/右下候选位。
- 折件正封面：41×41 面内，依据主体安全区选择左下、右下或右中。
- 折件背面：仅小型识别标题，主位保留给中文概念文案。
- 封底：标题区固定在曲目表上方；不进入条码、版权、曲目矩形。
- 两个 4.4mm 侧封：只用缩窄、竖排或旋转版，若最小可读尺寸不足则显示功能字体短标题。
- 内盘底：只用小型识别标题；中文主文案与英文副文案保持其已有区域。

## 交互

Visual DNA 完成后显示 Typography Direction。标题模块显示：原封面标题、普通字体、AI 艺术字三种模式；艺术字模式中始终显示 4 个候选卡位、重新生成、上传参考字、上传标题资产、选择方案。未配置 Provider 时“自动生成”说明原因，上传与已有候选选择仍可用。
