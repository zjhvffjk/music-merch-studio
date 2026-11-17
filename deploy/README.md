# 远程工作台与 MCP

网页：`https://music.haoquanwo.cloud/`，使用独立网页账号登录。
MCP：`https://music.haoquanwo.cloud/mcp`，Streamable HTTP，使用独立 Bearer Token。
适用于可设置 HTTP 请求头的 Agent 客户端；当前未实现 OAuth 登录流程。

## Dokploy 部署

创建独立项目与 Docker Compose 服务，Git 仓库使用本项目、分支 `master`，Compose 路径填写 `deploy/compose.yaml`。
域名的 A 记录指向服务器。Compose 内包含独立 Traefik 路由及自动 HTTPS 配置。
需要服务器现有的 `dokploy-network`、`web` / `websecure` 入口及 `letsencrypt` 证书配置。

持久文件放在 `/opt/music-merch-studio/outputs`，日志目录为 `/opt/music-merch-studio/logs`，属主为 UID 10001。
专用配置文件 `/opt/music-merch-studio/secrets.env` 仅允许管理员读取。Dokploy 的部署进程在容器内运行，还需将该文件复制到 `/etc/dokploy/compose/<服务AppName>/secrets.env`（位于Git代码目录外，重新拉取代码不会覆盖）。Compose默认从此共享目录读取；独立命令行部署可设置 `STUDIO_SECRETS_FILE` 指定文件路径。包含以下变量：

```
STUDIO_WEB_USER=studio
STUDIO_WEB_PASSWORD=<随机生成的独立密码，至少24字符>
STUDIO_MCP_TOKEN=<随机生成的独立令牌，至少24字符>
STUDIO_DOWNLOAD_SECRET=<随机生成的签名密钥，至少24字符>
```

不要将该文件提交到 Git，也不要复制本机加密的 AI 密钥到服务器。需要使用 AI 图片功能时，在服务器工作台单独配置。

## Agent 使用流程

1. `studio_status` 检查连接，`search_music` / `artist_albums` / `album_tracks` 查询音乐。
2. `upload_image` 上传封面（公网图片 URL 或 base64，最大20MB）。
3. `create_minicd` 提交1–12张专辑，可同时生成八视图。`generate_mockups` 为已有迷你CD项目补出图。
4. `create_merchandise` 调用原有播放界面、钥匙扣、白底商品图、黑胶及专辑卡生成。
5. `get_task` 每5–10秒查询进度。生成操作返回任务编号，单个串行队列最多容纳20个待处理或正在处理任务。
6. `get_downloads` 返回1小时有效的下载链接；可重新调用刷新。`list_projects` / `get_project` 查询保存的作品。

独立商品图8192×8192，总预览8192×4096。原素材清晰度及外壳照片的分辨率仍决定放大后的真实细节。
服务重启会保留任务记录及文件；未开始的任务继续排队，运行中的任务标记为中断，检查已生成文件后再重试。
网页版样机素材微调保存在各浏览器的本地存储中；MCP出图使用项目服务器上的素材和默认样机布局。

## 验证

安装部署依赖后执行 `python -m unittest discover -s tests -p test_remote_mcp.py -v`。
实际部署还需验证 HTTPS、标准 MCP 客户端握手、真实生成任务、下载文件尺寸和 ZIP 内容。
