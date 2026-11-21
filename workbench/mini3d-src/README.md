# Mini-CD 3D 预览原型

编译后可通过本地工作台的 `/mini3d/?review=shell` 查看空壳模型。`/mini3d/?jid=<项目编号>` 可从 `/api/design/file` 读取已有的独立印刷图，场景保存和单件替换仍需要接入 `/api/design/3d-config`。

```powershell
cd workbench/mini3d-src
npm ci
npm run build
```

用户确认外壳外尺寸为 53×45×8 mm（不含挂孔），左侧竖向铰链，打开后盒盖在左、盘托在右；两个挂孔闭合时重叠。`public/reference/` 保存空盒结构参考，`public/reference/final/` 保存用户后续给出的带专辑内容商品图，页面按闭合正面、闭合背面、平铺展开、斜向打开和展开取盘五种状态展示最终效果参考。参考图片需放到本地相应目录。当前模型可导出 2K/4K PNG 预览，但透明材质、模压细节与摄影灯光尚未达到参考图片的商品图质量。外尺寸虽已确认，铰链、卡扣、壁厚与纸件插入深度仍需实物校准，不应据当前预览模型开模。印刷尺寸仍以 `tools/spec_minicd.py` 为准。

Blender v6 和 v7 的描线参考可放在各自输出目录下的 `reference/shell-drawing.png`。
