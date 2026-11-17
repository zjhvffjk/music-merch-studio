# 工作台线上部署

工作台地址：`https://music.haoquanwo.cloud/`，使用独立网页账号登录。

Dokploy 独立项目从 GitHub 仓库 `master` 分支自动部署，Compose 文件为 `deploy/compose.yaml`。Traefik 提供 HTTPS。网页入口把请求转发到容器内运行的原版工作台，仓库中的设计、打印、八视图和导出功能使用同一份源码。

作品和上传文件保存在服务器 `/opt/music-merch-studio/outputs`；日志在 `/opt/music-merch-studio/logs`。容器用户 UID 为 10001。重新拉取 GitHub 代码不会覆盖这两个目录。

网页账号配置放在 `/etc/dokploy/compose/<服务AppName>/web.env`，只允许服务器管理员读取，内容为：

```
STUDIO_WEB_USER=studio
STUDIO_WEB_PASSWORD=<至少24字符的随机密码>
```

独立命令行部署可用 `STUDIO_WEB_ENV_FILE` 指向配置文件。不要把密码或本机 AI 密钥提交到 Git；服务器如需使用 AI 图片功能，应在网页中单独配置。

远程 MCP 已暂停，`/mcp` 和旧签名下载地址不再提供服务。工作台网页及原有 HTTP 功能仍需网页登录。

验证时检查 HTTPS、未登录访问被拒、登录后设计页和八视图页面可打开、项目和素材可读取，并确认原有其他站点不受影响。
