# Public APIs 候选研究报告

- 研究日期：2026-09-22
- 候选入口：[public-apis/public-apis](https://github.com/public-apis/public-apis)
- 范围：只做发现、官方文档复核与现有 Mini CD 工作台适配评估；未安装依赖、未配置密钥、未改动业务代码。

## 结论先行

公开 API 目录适合作为长期的发现入口，但不应成为某一个运行时依赖。当前工作台最需要保护的是“同一张专辑、同一发行版本”的数据一致性：封面、曲目、时长、发行日期、厂牌与版权信息必须来自同一个 release / album ID，再进入 Visual DNA 和包装排版。

当前中文歌手检索仍应保留既有 QQ / 网易云适配器作为中文主链路；公开目录中的全球资料源无法可靠替代它。它们适合做**可显示来源的补全、交叉校验和国际专辑备用来源**，不能把不同来源的封面、曲目和年份直接拼在一起。

本轮仅有 Google Fonts Developer API 达到 A 级“可直接规划接入”的条件。音乐、图像与 AI 候选均进入 B 或 C，原因是商业授权、覆盖范围、密钥、额度或版本一致性仍需在接入时逐项落实。

## 统一接入原则

1. 浏览器只调用工作台自己的服务；任何第三方 API Key、Apple developer token、OAuth refresh token 仅保存于服务器环境变量。
2. `albumCanonicalId` 先锁定来源与发行版本。后续封面、曲目、时长、发行日期和 label 只能跟随该 ID；补全来源只能写入 `supplemental`，不能静默覆盖主数据。
3. 每条资料保存 `provider`、`providerId`、`fetchedAt`、`rights`、`attribution` 和 `confidence`。不满足商用或署名要求的图片不得进入 Print Ready 成品。
4. 所有候选都通过 Provider 层：`MusicProvider`、`MetadataProvider`、`ImageProvider`、`TypographyProvider`、`ArtworkProvider`、`OcrProvider`。页面不直接请求第三方。
5. 下文“CORS”表示是否适合浏览器直连。即使对方允许跨域，本项目仍统一由服务器代理，避免暴露密钥并统一缓存、重试和审计。

## A：建议接入

### 1. Google Fonts Developer API — TypographyProvider / Font Library

| 项目 | 复核结果 |
| --- | --- |
| 官方 / GitHub | [官方文档](https://developers.google.com/fonts/docs/developer_api) · [字体仓库](https://github.com/google/fonts) |
| 可提供 | 字体家族、分类、子集/语言、字重与样式、可变字体轴、版本、文件 URL、最后修改日期。适合填充 Font Library 的 `fontFamily / style / language / weight / license / usageRole`。 |
| Key / OAuth | 需要 Google API Key；不需要 OAuth。Key 按项目规则只放服务器环境变量。 |
| 费用 / 额度 | API 使用不收费；配额在 Google Cloud 项目中管理，官方页面未给出一个固定公共数值。 |
| HTTPS / CORS | HTTPS；不依赖浏览器 CORS，服务器拉取并缓存字体元数据。 |
| 商用 | Google Fonts 明确说明全部字体为开源许可，可用于商业和非商业项目；每个实际下载字体仍要把具体 OFL/Apache/UFL 等许可证写入本地 Font Library。 |
| 维护 / 文档 | 官方 Google 文档可用，返回项含 `lastModified` 与文件信息。 |
| 适配判断 | **A。** 只做“字体发现、授权记录、真实字体渲染”的资料来源；不替代 AI 艺术字，也不允许自动下载后跳过许可证记录。 |

## B：备用 Provider 或需条件接入

### 音乐资料

| API | 官方 / GitHub | 能提供什么 | Key / 费用 / 限制 | HTTPS / CORS / OAuth | 商业与维护状态 | 适合的模块与结论 |
| --- | --- | --- | --- | --- | --- | --- |
| MusicBrainz + Cover Art Archive | [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API) · [速率规则](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting) · [Cover Art Archive](https://musicbrainz.org/doc/Cover_Art_Archive/API) · [GitHub](https://github.com/metabrainz/musicbrainz-server) | Artist、release/release-group、曲目、序号、时长、日期、标签、ISRC/条码等 MusicBrainz ID；CAA 用 release MBID 返回封面与缩略图。 | 公共 API 不要求 Key；官方公共服务要求有意义的 User-Agent，最多 **1 请求/秒/IP**，必须服务器缓存、队列化。 | HTTPS；公共读取端点通常可跨域，但仍统一服务器调用；不需 OAuth。 | 官方明确公共服务供非商业用途；商用计划需联系 MusicBrainz。CAA 图片必须遵守其来源/权利信息。文档与项目持续维护。 | **B。** 作为国际专辑的 MetadataProvider 与版本校验来源。不得把它当中国曲库主来源，也不能默认把 CAA 封面当可印刷商用素材。 |
| Apple Music API | [官方文档](https://developer.apple.com/documentation/AppleMusicAPI) | 目录搜索，artist、album、song、tracklist、曲目序号、artwork、release date、genre、录音资料和 Apple catalog ID；可按 storefront 检索。 | 需要 developer token（服务端 JWT）；读取公共 Catalog 不需要用户 OAuth，访问个人库才需要 Music User Token。无公开固定免费调用量；按 HTTP 429 与响应头做限流。 | HTTPS；应服务端调用；个人库场景才 OAuth。 | 官方文档持续维护。使用条款、可用地区和目录展示权利需要接入时二次确认。 | **B。** 国际正规目录候选，适合 `AppleMusicProvider`。只有专辑搜索结果来自 Apple 时，才可整包使用其同一 catalog album ID 的曲目和封面。 |
| Discogs API | [API 条款与数据字段](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use) · [GitHub 客户端](https://github.com/discogs/discogs_client) | Release/master、发行日期、format、tracklisting、条码与外部标识、artist、版本、部分 label/credits/genre/style 和社区封面。 | 需要 token 或 OAuth；无固定公开额度承诺，应读取限流响应并节流。 | HTTPS；服务端调用；OAuth 可选，取决于端点。 | 标题、日期、format、tracklist、barcode 等 CC0 数据有价值；图片和其他 Restricted Data 受限。必须显示 Discogs 数据声明与链接；数据不可长期缓存，官方要求不超过提供服务所必需时长。 | **B。** 适合 `ReleaseMetadataProvider` 做实体唱片版本、条码/厂牌核验；不作为包装封面图片来源，也不作为长期镜像库。 |
| Apple iTunes Search API | [官方文档](https://performance-partners.apple.com/search-api) | 简单 Search/Lookup，album、artist、歌曲、封面、部分曲目和 UPC lookup。 | 无 Key、无 OAuth；官方没有固定调用额度，需保守缓存。 | HTTPS；服务器调用。 | Apple 将 API 内的专辑图等定位为推广商店内容；不适合拿来做实体包装成品图片。文档仍可用。 | **B（仅元数据验证）。** 可作为无密钥的低成本查找备用；不承担版权区、厂牌或 Print Ready 封面。 |

### 图片、设计与素材

| API | 官方 / GitHub | 能提供什么 | Key / 费用 / 限制 | HTTPS / CORS / OAuth | 商业与维护状态 | 适合的模块与结论 |
| --- | --- | --- | --- | --- | --- | --- |
| Pexels API | [API 文档入口](https://www.pexels.com/api/) · [免费与额度](https://help.pexels.com/hc/en-us/articles/47677890260761-Is-the-Pexels-API-free-to-use) · [API 条款](https://help.pexels.com/hc/en-us/articles/900005880463-What-are-the-Terms-and-Conditions) | 照片/视频搜索、标签、作者、尺寸、下载 URL，适合 moodboard 或背景灵感检索。 | API Key；免费。默认 **200 次/小时、20,000 次/月**，可申请提高。 | HTTPS；Key 不可前端暴露，服务器代理；无需 OAuth。 | 图片可商用，但 API 条款禁止把未经过有实质创作加工的素材作为实体印刷品出售；还要求平台内署名，且禁止拿数据训练 AI。文档在持续更新。 | **B。** 只作带作者署名的灵感板/可选素材候选。不能自动进入 Mini CD 成品，更不能作为“原始专辑封面”。 |
| Openverse API | [官方 API 文档](https://docs.openverse.org/) · [GitHub](https://github.com/WordPress/openverse) | 公开许可图片/音频搜索，返回 source、license、creator、URL、尺寸等，可按许可过滤。 | 匿名可调用；可用 OAuth client credentials 增强访问；固定免费额度未公布，需读取 rate-limit headers。 | HTTPS；可用 JS API client，但本项目仍服务器调用。 | 聚合了 CC/公版素材；Openverse 明确不保证条目许可证准确，使用者必须逐项验证并按许可署名，商业/重负载未来可收费。持续维护。 | **B。** `LicensedAssetProvider` 的候选，只允许 CC0 或经人工确认的 CC BY 资产进入可售印刷成品。 |
| The Color API | [官方文档](https://www.thecolorapi.com/docs) · [GitHub](https://github.com/joshbeckman/thecolorapi) | 给定 HEX/RGB/HSL/CMYK 返回颜色名、转换值、对比色及单色/互补/三色等色板，支持 JSON 与 SVG。 | 无 Key、免费；官方没有稳定 SLA 或公开速率配额。 | HTTPS，文档说明支持 JSONP；服务器调用即可；无 OAuth。 | 小型服务，文档当前可用但缺少企业级 SLA 和清晰商业服务承诺。 | **B。** 只能作为 Visual DNA 取色后的“色板建议”备用，绝不能替代本地色彩分析或作为唯一生产依赖。 |

### AI、图像处理与 OCR

| API | 官方 / GitHub | 能提供什么 | Key / 费用 / 限制 | HTTPS / CORS / OAuth | 商业与维护状态 | 适合的模块与结论 |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI API（图像、视觉、文本、Embedding） | [快速开始](https://platform.openai.com/docs/quickstart/make-your-first-api-request) · [图像生成/编辑](https://platform.openai.com/docs/api-reference/images-streaming/image_generation/partial_image) · [价格](https://openai.com/api/pricing/) | Artwork 生成/编辑、透明 PNG 输出、封面视觉分析、Concept Copy、title lettering 候选提示、Embedding 检索。 | API Key；按量付费，没有可依赖的长期免费额度。当前图像模型按输入/输出 token 计费。需要服务器限额、任务队列、成本记录。 | HTTPS；严格服务器调用；无 OAuth。 | 官方 API 与文档持续维护，适合商业产品，但输出仍需经过版权、商标、人物和内容审核。 | **B。** 是已规划的 `ArtworkProvider`、`TypographyProvider`、`VisionProvider` 的高质量后续实现，不在本阶段接付费 API。透明背景能力可用于未来真实 AI Artistic Typography 的四候选资产。 |
| Hugging Face Inference Providers | [官方文档](https://huggingface.co/docs/inference-providers/) · [计费说明](https://huggingface.co/docs/inference-providers/pricing) · [GitHub SDK](https://github.com/huggingface/huggingface_hub) | 一个统一接口路由文本、图像生成、embedding、分类等多个模型/Provider，可做低成本实验与多 Provider 备用。 | 需要 HF token；免费账号当前每月 **$0.10** 实验额度，超额按量付费；模型和底层 Provider 许可证必须单独审核。 | HTTPS；服务器调用；不需要用户 OAuth。 | 平台与文档活跃，但“能调用”不等于模型允许商用，单模型的 license/数据条款必须进入审核。 | **B。** 适合未来 Provider sandbox 与 Embedding/实验模型备选，不宜作为默认生产艺术字来源。 |
| remove.bg | [API 文档](https://www.remove.bg/a/api-docs) | 抠图、透明背景，适合用户上传参考字、标题裁切候选、人物/主体分离。 | API Key；免费与自助套餐均有额度，具体赠送次数和价格须在开通当天按账户页面确认。 | HTTPS；服务器调用；无 OAuth。 | 商业服务、官方文档可用；输出许可和存储政策在接入前再审。 | **B。** 可以成为 `ImageProcessingProvider.removeBackground()` 的候选，尤其服务于 cover-title-reference extraction；不接入前不改变现有本地流程。 |
| OCR.space | [官方文档与额度](https://ocr.space/ocrapi) · [商业使用 FAQ](https://ocr.space/faq) | 图片/PDF OCR、简繁中文、文字坐标 overlay、方向/手写引擎。 | API Key；免费 **500 次/日/IP、25,000 次/月**（Engine 1/2），Engine 3 另有 2,500 次/月；PRO $30/月起。 | HTTPS；应服务器调用；无 OAuth。 | 免费计划允许商用但没有 uptime 保证；官方文档当前可用。 | **B。** 作为当前本地 OCR 的云端备用，仅用于封面标题识别失败时；原图默认不外发，须由用户或隐私策略允许。 |

## C：仅参考，不建议接入当前工作台

| API / 服务 | 依据与不接入原因 |
| --- | --- |
| Spotify Web API | [官方限制说明](https://developer.spotify.com/documentation/web-api/concepts/quota-modes) 显示开发模式受用户与用途限制、生产扩展需审核；还需要 OAuth 或 Client Credentials，曲库许可和封面使用限制不适合作为包装生产资料。可参考其 API 模型，不应作为本工作台主/备数据源。 |
| TheAudioDB | [官方 API 页面](https://www.theaudiodb.com/api_guide.php) 适合娱乐资料补全，但免费 key、数据完整性与中文发行版本覆盖不足；不能提供可稳定核验的完整 album release 链路。 |
| Jamendo | [官方 API](https://developer.jamendo.com/v3.0) 的核心是其独立音乐/许可目录，不覆盖主流或中文专辑；与“搜歌手真实专辑并复原 metadata”目标不匹配。 |
| Unsplash Source / API | [官方 API 指南](https://help.unsplash.com/en/articles/2511258-guideline-triggering-a-hotlink) 对图片展示、hotlink、署名和 API 使用有专门要求。虽然可用于灵感，但无法解决包装印刷的权利清链路；与 Pexels 相比没有额外必要性。 |
| Iconify / 图标聚合 API | [官方文档](https://iconify.design/docs/api/) 解决的是 UI icon，而不是唱片视觉或艺术字；每个图标集许可证不同。可按 UI 需要日后挑选，不建进当前 Album Design Provider。 |
| Adobe Express、Canva、ArtFont、标智客 | 它们是用户体验/效果参考，不是本阶段的稳定公共 API 候选；不能爬取或把网页自动化当 Provider。ArtFont 输出是 artwork 而非可安装字体，Canva/Adobe 的文字效果也不等价于可复用的标题资产。它们继续保留在 AI Artistic Typography 的产品参考清单中。 |

## 推荐的数据链路（不执行）

### 中文专辑

```text
现有 QQ / 网易云适配器（主来源，锁定 source + album ID）
  └─ 得到封面、前 10 首、时长、发行日、厂牌/公司
      ├─ 若缺发行版本字段：Discogs / MusicBrainz 仅按 artist + album + date + track count 做候选核验
      └─ 若无法达到高置信度：保留“资料待确认”，不能拿另一个版本覆盖
```

### 国际专辑

```text
AppleMusicProvider（主来源；锁定 storefront + catalog album ID）
  └─ 同 ID 获取曲目、时长、日期、genre、官方 artwork
      ├─ MusicBrainzProvider：外部 ID/版本交叉核验
      └─ DiscogsProvider：实体发行、label、barcode 补全，且标注来源与数据时效
```

`ArtworkProvider` 与 `MusicProvider` 分离：原始专辑封面只用音乐来源返回的封面作为 Visual DNA 参考，不能把 Pexels/Openverse 素材伪装成原始封面。用于新包装背景的素材则必须走 `LicensedAssetProvider`，携带授权与署名记录。

## 建议的最小 Provider 契约（以后再做）

```ts
interface MusicProvider {
  searchArtists(query: string): Promise<ArtistHit[]>
  searchAlbums(artistId: string, query?: string): Promise<AlbumHit[]>
  getAlbum(albumId: string, options?: { storefront?: string }): Promise<CanonicalAlbum>
}

interface MetadataProvider {
  enrich(candidate: CanonicalAlbum): Promise<SupplementalMetadata>
}

interface TypographyProvider {
  listFonts(filter: FontFilter): Promise<LicensedFont[]>
}

interface ImageProvider {
  searchLicensedAssets(query: string): Promise<LicensedAsset[]>
}

interface ArtworkProvider {
  generate(request: ArtworkRequest): Promise<ArtworkCandidate[]>
}
```

`CanonicalAlbum` 必须含：`provider`、`providerAlbumId`、`artist`、`title`、`coverUrl`、`releaseDate`、`genre[]`、`tracks[{number,title,durationMs,externalIds}]`、`externalIds`、`editionKey`。`SupplementalMetadata` 不可覆写主来源字段，只能带 `fieldProvenance` 和 `confidence`，由规则或用户确认后合并。

## 真正值得进入后续排期的项目

1. **Google Fonts metadata 同步与 Font Library 授权记录**：唯一 A 级；服务 Typography System 的真实字体渲染。
2. **音乐数据的版本一致性层**：先不换当前搜索；先设计 `CanonicalAlbum + provenance`，再选择 MusicBrainz / Apple / Discogs 之一做备用。
3. **AI Provider 的成本与权限层**：OpenAI 和 HF 只放在既有 Provider 架构的 Phase 2，配置 `dailyBudget`、每次生成成本、失败回退与人工选择。
4. **素材授权卡片**：若未来接 Pexels/Openverse，UI 必须显示作者、来源、许可、是否可印刷、是否已获确认；没有这层不能接入生产导出。

## 未做事项

- 未请求或保存任何 API Key、OAuth、账号授权或付费订阅。
- 未安装 SDK、未写 Provider、未改 UI、未改现有 QQ/网易云音乐检索逻辑。
- 未将第三方封面、图片或字体下载进项目。
