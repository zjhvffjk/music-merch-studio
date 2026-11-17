# 工作台线上部署

工作台地址：`https://music.haoquanwo.cloud/`，直接打开，无网页登录。

Dokploy 独立项目从 GitHub 仓库 `master` 分支自动部署，Compose 文件为 `deploy/compose.yaml`。Traefik 提供 HTTPS。网页入口把请求转发到容器内运行的原版工作台，仓库中的设计、打印、八视图和导出功能使用同一份源码。

作品和上传文件保存在服务器 `/opt/music-merch-studio/outputs`；日志在 `/opt/music-merch-studio/logs`。容器用户 UID 为 10001。重新拉取 GitHub 代码不会覆盖这两个目录。

不要把本机 AI 密钥提交到 Git；服务器如需使用 AI 图片功能，应在网页中单独配置。

远程 MCP 已暂停，`/mcp` 和旧签名下载地址不再提供服务。

验证时检查 HTTPS、无需登录即可打开设计页和八视图页面、项目和素材可读取，并确认原有其他站点不受影响。
