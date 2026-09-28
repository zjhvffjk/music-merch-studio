# 拾音工坊 · 音乐周边制作

本项目是一个本地运行的音乐周边制作工作台。输入歌手、歌曲或专辑后，可生成播放界面、钥匙扣商品图、白底电商图、黑胶播放图、迷你 CD 设计和印刷文件。

所有生成内容和作品库都保存在本机；工作台默认只监听 `127.0.0.1`，不会暴露到公网。

## 功能

- 搜索歌手、单曲与专辑，自动在网易云音乐与 QQ 音乐间补全数据。
- 制作歌曲播放界面、A4 印刷拼版和对折播放卡。
- 制作钥匙扣商品主图与白底 / 透明底电商图。
  - `长条透明款`
  - `透明方形圆环款`
- 制作黑胶播放界面、专辑封面母版和专辑卡。
- 迷你 CD 三件套设计、高清预览、导出和生产印刷文件。
- 作品库回看、下载 ZIP，以及将不需要的作品移入回收站。

本仓库是当前工作台 `music-merch-studio`。如果同时看到
[`music-keychain-studio`](https://github.com/zjhvffjk/music-keychain-studio)，
在另一台电脑部署这里的工作台时，请使用下方的 `music-merch-studio` 克隆地址。

## 在另一台 Windows 电脑部署

### 1. 准备软件

安装以下软件：

- [Git for Windows](https://git-scm.com/download/win)
- Python 3.10 或更高版本。安装时勾选 **Add Python to PATH**。

安装后打开 PowerShell，确认：

```powershell
git --version
python --version
```

### 2. 下载项目

在希望存放项目的目录打开 PowerShell：

```powershell
git clone https://github.com/zjhvffjk/music-merch-studio.git
cd music-merch-studio
```

### 3. 建立项目环境并安装依赖

只需第一次执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 启动

双击项目根目录的 **`启动工作台.bat`**。

浏览器没有自动打开时，访问：

```text
http://127.0.0.1:8765/
```

首次搜索、封面下载和音乐数据查询需要联网；已经生成的作品、上传的封面和输出文件都保留在本机。
GitHub 仓库只包含项目源码与所需素材，不包含你在本机生成的 `outputs` 作品数据。

## 日常使用

1. 搜索歌手、单曲或专辑。
2. 选择要制作的歌曲，勾选需要的商品。
3. 在“钥匙扣商品图款式”中选择 `长条透明款` 或 `透明方形圆环款`。
   此选择会同时作用于钥匙扣商品主图和白底 / 透明底电商图。
4. 点击开始制作，在结果页查看、下载或进入作品库回看。

### 下载图片和打印文件

- 下载 ZIP 时可选择 **JPG**、**PNG** 或 **原始格式**；默认 JPG。选择 JPG 时，透明区域会变为白底。
- 播放界面的 A4 打印拼版以 **600 DPI** 生成，每首歌有独立的 JPG 和 PDF。ZIP 中的打印图片固定为 JPG，PDF 会保留，不受前面的图片格式选项影响。
- 默认打印拼版是 A4 竖版、每页 **4 列 × 8 行 = 32 张**；每张成品为 **30 × 50 mm**，在拼版中旋转摆放。同一列的两张播放界面紧贴成一组，组与组之间及相邻列之间留有 1 像素裁切通道；外侧裁切参考线延伸到纸张留白区。
- 另可选竖向直排 30 张或横向留缝 21 张，也可制作对折播放卡。打印时请选择 **100%／实际大小**，不要使用“适应页面”，并先核对成品尺寸再批量裁切。

生成文件位于：

```text
outputs\工作台\
outputs\迷你CD设计\
```

## 更新项目

在项目目录打开 PowerShell：

```powershell
git pull origin master
```

更新代码后，关闭旧工作台窗口，再双击 `启动工作台.bat` 重新启动。

## 可配置项

- `config/canvas_presets.json`：白底商品图的画布尺寸与留白比例。
- `assets/keychain/`：钥匙扣外壳贴片素材。
- `assets/fonts/`：迷你 CD 设计使用的字体库。

修改画布或贴片后，需要重启工作台。

## 常见问题

### 双击启动后提示缺少模块

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 浏览器打不开或端口被占用

关闭已有的工作台窗口后重新双击 `启动工作台.bat`。也可以在 PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe workbench\server.py --force
```

### 搜索不到歌曲或封面

确认网络正常后重试。工作台会自动尝试网易云音乐和 QQ 音乐；部分版权歌曲可能没有可用封面。

### 如何备份作品

复制整个 `outputs` 文件夹即可，其中包含成品、作品库记录和上传封面。换电脑时，把旧电脑的 `outputs` 复制到新电脑项目根目录，再启动工作台；单纯 `git clone` 或 `git pull` 不会带回这些数据。

## 开发验证

安装依赖后可运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
