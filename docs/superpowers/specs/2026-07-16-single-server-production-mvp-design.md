# 单机生产上线 MVP 设计

## 目标

将当前 FastAPI + SQLite 资产管理系统收敛为适合少于 10 名并发写入用户的单机部署版本。服务由 Nginx 反向代理，应用仅监听本机回环地址。当前可用公网 IP 进行 HTTP 连通性验证；正式对外使用前必须接入域名和 HTTPS。

## 范围

本轮实现以下能力：

- 生产环境强制配置 JWT 密钥，并取消代码、页面和启动日志中的默认管理员密码暴露。
- 增加数据库可用性健康检查。
- 将 SQLite 配置为单进程、WAL、外键约束和有限写入等待。
- 增加独立测试依赖和针对本轮行为的自动化测试。
- 提供 Nginx、systemd 与环境变量示例，应用端口仅对本机开放。

本轮不引入 PostgreSQL、ORM 迁移框架、后台任务、前端构建流程或路由拆分。现有业务接口和 SQLite 数据文件格式保持兼容。

## 运行配置

新增一个后端配置模块，集中读取并校验环境变量，避免 `auth.py`、`main.py` 和 `start.py` 各自解析配置。

- `ENV=production` 时必须提供非空 `JWT_SECRET_KEY`，否则启动失败。
- 不再提供默认 `DEFAULT_ADMIN_PASSWORD`。首次初始化数据库且不存在 `admin` 用户时，必须提供该变量；数据库已有管理员时不要求此变量。
- 同源 Nginx 部署不需要 CORS。生产环境只有显式设置 `CORS_ORIGINS` 时才启用 CORS，且拒绝通配符来源。
- 支持 `DATABASE_URL` 覆盖默认 SQLite 路径，供隔离测试和未来部署使用；未设置时继续使用项目目录中的 `asset_lifecycle.db`。

`start.py --production` 继续作为便捷入口，但生产约束由环境变量和配置校验本身保证，不能因改用其他启动命令而绕过。

## 认证与凭据

删除启动日志中的管理员密码输出，移除登录页中的默认账号密码提示。`.env.example` 仅保留变量说明和空值，不包含可登录密码。`backend/.jwt_secret`、`.env`、数据库和运行日志继续由 `.gitignore` 排除；部署时生成新的 JWT 密钥，不复用当前本地密钥。

JWT 仍使用现有 Bearer Token 方式。本轮不更换为 Cookie 会话或刷新令牌机制，因为公网 HTTP 无法安全承载任何登录凭据；域名和 HTTPS 到位后再处理传输层安全与会话策略。

## 健康检查与 SQLite

新增无认证 `GET /api/health`。它执行轻量数据库查询并返回服务版本和数据库状态；数据库不可用时返回 HTTP 503。该接口供 systemd 启动后检查和 Nginx 反向代理验证使用，不返回密钥、路径或异常细节。

SQLite 连接启用 `foreign_keys=ON`、`journal_mode=WAL` 和 `busy_timeout`，并设置 SQLAlchemy 的 SQLite 连接超时。部署使用单个 Uvicorn worker，避免多进程写入 SQLite。数据库继续由文件系统定期备份，升级或部署前先执行完整性检查和备份。

## 测试设计

新增 `requirements-dev.txt`，在生产依赖基础上安装 `pytest` 和 FastAPI 测试客户端所需依赖。新增独立测试模块，使用临时 SQLite 数据库和环境变量覆盖，避免读取或修改开发数据库。

测试覆盖：

- 生产环境缺少 JWT 密钥时拒绝启动。
- 首次生产初始化缺少管理员密码时拒绝初始化。
- 显式配置密钥和管理员密码时可初始化。
- 健康检查在数据库可用时返回 200，在数据库不可用时返回 503。
- SQLite 连接启用外键、WAL 与写入等待配置。
- 页面、启动脚本和示例环境文件不包含默认管理员密码。

现有依赖真实服务、旧账号密码或旧字段的功能脚本不作为本轮发布门禁；后续单独重建端到端测试。

## 部署模板

新增 `deploy/` 目录：

- `deploy/systemd/asset-lifecycle.service`：以非 root 用户启动单个 Uvicorn 进程，读取受保护环境文件，只监听 `127.0.0.1:8000`。
- `deploy/nginx/asset-lifecycle.conf`：监听 HTTP 80，将请求代理到本机应用，并设置必要的转发头和上传大小限制。
- `deploy/README.md`：说明防火墙只开放 SSH 与 HTTP、Uvicorn 端口不对公网开放、数据库备份与恢复步骤，以及 HTTP 仅用于短期验证的限制。

当域名可用后，部署配置改为 HTTPS 并将 HTTP 重定向到 HTTPS；在此之前不得将当前 HTTP 公网地址视为安全生产入口。

## 验收标准

- 生产启动缺少 `JWT_SECRET_KEY` 时失败，且错误信息不泄露敏感值。
- 新库首次启动缺少 `DEFAULT_ADMIN_PASSWORD` 时失败；提供安全值时能创建管理员。
- 源码、启动日志和页面不再显示可用管理员密码；Git 未跟踪数据库、JWT 密钥或 `.env`。
- `GET /api/health` 在正常数据库上返回 200，在失效数据库上返回 503。
- 全部新增测试可在干净 Python 环境执行，且不修改项目数据库。
- systemd 服务仅监听本机地址，Nginx 是唯一的 HTTP 入口。
