# IT资产全生命周期管理系统 — 生产部署实施指南

> **版本**: v3.0.0 | **适用场景**: 长乐东南数据中心 | **修订日期**: 2026-07-03

---

## 1. 系统概述

| 项目 | 说明 |
|------|------|
| 系统名称 | IT资产全生命周期管理系统 |
| 目标场景 | 长乐东南数据中心（1618台设备） |
| 技术栈 | FastAPI + SQLAlchemy + SQLite + Vue3 (单文件SPA) |
| 默认端口 | 8000 |
| 版本 | v3.0.0 |

### 核心功能模块
- 资产台账（7阶段生命周期门禁）
- 采购入库 / 资产移入 / 资产移出
- 变更迁移 / 故障维修 / 维保续保 / 退役报废
- 审批工作流（6类型审批 + 手动指定审批人 + 故障降级）
- 导入导出（8类子表模板/导出/导入）
- RBAC权限管理（4预设角色 + 50项细粒度权限）
- 数据校验仪表盘 + 综合报表

---

## 2. 部署前置条件

### 2.1 系统要求

| 项目 | 最低要求 |
|------|---------|
| 操作系统 | Linux (CentOS 7+/Ubuntu 20+) 或 Windows Server 2016+ |
| Python | 3.10+ |
| 内存 | ≥ 2GB |
| 磁盘 | ≥ 500MB（含数据库预留空间） |
| 网络 | 内网可访问，如需外网访问需配置反向代理 |

### 2.2 Python依赖包

```
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
pyjwt>=2.8.0
passlib>=1.7.4
bcrypt>=4.1.0
openpyxl>=3.1.0
python-multipart>=0.0.6
```

---

## 3. 安装步骤

### 3.1 获取项目文件

```bash
# 从版本库获取
git clone <repository-url> asset-lifecycle-manager
cd asset-lifecycle-manager

# 或从交付包解压
tar xzf asset-lifecycle-manager.tar.gz
cd asset-lifecycle-manager
```

### 3.2 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux
# venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3.3 配置JWT密钥（关键步骤）

JWT密钥优先级：**环境变量 > .jwt_secret配置文件 > 开发随机密钥**

生产环境**必须**提供固定密钥，否则服务拒绝启动。

```bash
# 方式1：生成密钥写入配置文件（推荐）
python -c "import secrets; print(secrets.token_hex(32))"
# 将输出值写入 backend/.jwt_secret 文件
echo "a951d52c877794065727d54be0c16c3ca953907c3aa9611fe9d806c1ddbadbb5" > backend/.jwt_secret

# 方式2：设置环境变量
export JWT_SECRET_KEY="a951d52c877794065727d54be0c16c3ca953907c3aa9611fe9d806c1ddbadbb5"

# ⚠️ .jwt_secret 和 .jwt_dev_key 文件不应进入版本库（已配置.gitignore）
```

### 3.4 配置管理员密码

```bash
# 修改默认管理员密码（可选，首次启动后也可通过系统界面修改）
export DEFAULT_ADMIN_PASSWORD="YourStrongPassword123!"

# 默认账号: admin / Admin@2026!Secure
```

### 3.5 配置CORS来源（如需外部访问）

```bash
# 生产环境限定具体域名
export CORS_ORIGINS="http://your-domain.com,https://your-domain.com"
```

---

## 4. 数据库初始化

### 4.1 首次启动（自动建表+初始化）

系统使用SQLite，首次启动时自动创建数据库文件和所有表结构，并初始化：
- 4个预设角色（系统管理员/运维主管/运维工程师/只读用户）
- 1个默认管理员账号（admin）
- 50项权限定义

```bash
# 确认不存在旧数据库
rm -f asset_lifecycle.db  # 仅首次部署时执行

# 启动服务（自动建表）
python start.py --production
```

启动后日志应显示：
```
运行模式: PRODUCTION
启动地址: http://0.0.0.0:8000
JWT密钥来源: 配置文件(.jwt_secret)
默认管理员账号: admin / <密码>
```

### 4.2 数据库文件位置

```
asset-lifecycle-manager/
├── asset_lifecycle.db          # SQLite数据库（自动创建）
├── backend/
│   ├── .jwt_secret             # 生产JWT密钥（手动配置）
│   ├── database.py             # ORM模型定义
│   ├── auth.py                 # JWT+RBAC认证
│   └── ...
```

### 4.3 数据导入（可选）

首次部署后如需导入历史资产数据，通过系统界面的"数据交换"模块操作：
1. 下载导入模板（8类：资产/采购/移入/移出/变更/故障/维保/退役）
2. 按模板格式填写数据
3. 上传Excel导入

---

## 5. 启动与停止

### 5.1 启动命令

```bash
# 开发模式（默认）
python start.py

# 生产模式
python start.py --production

# 指定绑定地址和端口
python start.py --production --host 0.0.0.0 --port 8000

# 后台运行（Linux）
nohup python start.py --production --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

### 5.2 停止服务

```bash
# 前台运行：Ctrl+C

# 后台运行
ps aux | grep "start.py" | grep -v grep | awk '{print $2}' | xargs kill

# Windows
taskkill /F /IM python.exe /FI "WINDOWTITLE eq asset*"
```

### 5.3 systemd服务配置（Linux推荐）

创建 `/etc/systemd/system/asset-lifecycle.service`：

```ini
[Unit]
Description=IT Asset Lifecycle Management System
After=network.target

[Service]
Type=simple
User=assetmgr
Group=assetmgr
WorkingDirectory=/opt/asset-lifecycle-manager
Environment=ENV=production
Environment=JWT_SECRET_KEY=<your-secret-key>
Environment=DEFAULT_ADMIN_PASSWORD=<your-admin-password>
ExecStart=/opt/asset-lifecycle-manager/venv/bin/python start.py --production --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable asset-lifecycle
sudo systemctl start asset-lifecycle

# 查看状态
sudo systemctl status asset-lifecycle

# 查看日志
sudo journalctl -u asset-lifecycle -f
```

---

## 6. Nginx反向代理配置

生产环境推荐使用Nginx反向代理，提供HTTPS、限流、静态文件缓存。

### 6.1 Nginx配置示例

```nginx
server {
    listen 80;
    server_name asset.your-domain.com;

    # 强制HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name asset.your-domain.com;

    ssl_certificate     /etc/nginx/ssl/your-domain.crt;
    ssl_certificate_key /etc/nginx/ssl/your-domain.key;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    # 前端静态文件（缓存优化）
    location /static/ {
        proxy_pass http://127.0.0.1:8000/static/;
        proxy_set_header Host $host;

        # 静态资源缓存
        location /static/*.js {
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
        location /static/*.css {
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
    }

    # API请求
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 限流（防止暴力登录）
        limit_req zone=api burst=20 nodelay;

        # 请求体大小（导入Excel文件可能较大）
        client_max_body_size 10m;
    }

    # 首页
    location / {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API文档（生产环境可选关闭）
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        # 生产环境可限制访问IP
        # allow 10.0.0.0/8;
        # deny all;
    }
}

# 限流区域定义（在http块中）
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

---

## 7. 安全注意事项

### 7.1 密钥管理

| 项目 | 说明 |
|------|------|
| JWT密钥 | 生产必须固定（`.jwt_secret`文件或环境变量），密钥更换后所有已登录Token失效 |
| 密钥文件权限 | `chmod 600 backend/.jwt_secret`（仅服务账户可读） |
| 密钥不在版本库 | `.gitignore`已排除 `.jwt_secret` 和 `.jwt_dev_key` |
| 管理员密码 | 首次登录后立即修改默认密码，bcrypt哈希存储 |
| Token过期 | 24小时自动过期 |

### 7.2 数据库安全

| 项目 | 说明 |
|------|------|
| SQLite文件权限 | `chmod 600 asset_lifecycle.db` |
| 外键约束 | 已启用PRAGMA foreign_keys=ON |
| 用户删除 | 软删除（status→disabled），不物理删除记录 |
| 备份 | 每日自动备份（见第8节） |

### 7.3 网络安全

| 项目 | 说明 |
|------|------|
| CORS | 生产环境限定具体域名，禁止 `*` |
| HTTPS | 通过Nginx反向代理强制HTTPS |
| 登录限流 | Nginx层限制10r/s |
| API文档 | `/docs` 生产环境可限制IP访问 |

### 7.4 等保合规要点

- 访问控制：RBAC 50项细粒度权限 + 4角色体系
- 审计追溯：操作审计日志（AuditLog表）
- 传输安全：HTTPS强制 + JWT Token认证
- 数据完整性：阶段门禁校验 + 13项业务校验规则
- 账号安全：bcrypt哈希 + 24h Token过期 + 软删除

---

## 8. 备份与恢复

### 8.1 数据库备份策略

```bash
# 每日全量备份脚本（加入cron）
BACKUP_DIR="/opt/backups/asset-lifecycle"
DB_FILE="/opt/asset-lifecycle-manager/asset_lifecycle.db"
DATE=$(date +%Y%m%d)

# SQLite安全备份（使用vacuum into，不锁库）
python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_FILE')
conn.execute('VACUUM INTO \"$BACKUP_DIR/asset_lifecycle_$DATE.db\"')
conn.close()
print('Backup completed: asset_lifecycle_$DATE.db')
"

# 保留7天备份
find $BACKUP_DIR -name "asset_lifecycle_*.db" -mtime +7 -delete
```

### 8.2 数据恢复

```bash
# 停止服务
sudo systemctl stop asset-lifecycle

# 替换数据库文件
cp /opt/backups/asset-lifecycle/asset_lifecycle_20260703.db \
   /opt/asset-lifecycle-manager/asset_lifecycle.db

# 重启服务
sudo systemctl start asset-lifecycle
```

### 8.3 密钥文件备份

```bash
# JWT密钥文件同样需要备份（密钥丢失 = 所有Token失效）
cp backend/.jwt_secret /opt/backups/asset-lifecycle/jwt_secret_backup
```

---

## 9. 项目文件清单

### 生产部署必需文件

| 文件 | 路径 | 说明 |
|------|------|------|
| 启动脚本 | `start.py` | 一键启动（支持--production/--host/--port） |
| 依赖清单 | `requirements.txt` | 7个Python依赖包 |
| 环境变量示例 | `.env.example` | 参考配置模板 |
| Git忽略规则 | `.gitignore` | 排除.db/.jwt_secret等敏感文件 |
| 前端页面 | `frontend/index.html` | Vue3单文件SPA |
| 主路由 | `backend/main.py` | FastAPI应用入口 |
| 数据模型 | `backend/database.py` | ORM模型 + 表结构 |
| 认证权限 | `backend/auth.py` | JWT+RBAC + 角色定义 |
| 审批引擎 | `backend/approval.py` | 6类型审批工作流 |
| 数据校验 | `backend/validation.py` | 13项校验 + 阶段门禁 |
| 常量配置 | `backend/constants.py` | 枚举选项 + 审批链 |
| 数据模型 | `backend/schemas.py` | Pydantic请求/响应模型 |
| 导入导出 | `backend/import_export_reports.py` | 8类模板/导入/导出/报表 |
| JWT密钥 | `backend/.jwt_secret` | **生产部署需手动生成** |

### 部署后自动生成的文件

| 文件 | 说明 |
|------|------|
| `asset_lifecycle.db` | SQLite数据库（自动建表+初始化） |

---

## 10. 验收检查清单

部署完成后，逐项验证：

| # | 检查项 | 验证方式 | 预期结果 |
|---|--------|---------|---------|
| 1 | 服务启动 | `curl http://localhost:8000/` | 返回HTML前端页面 |
| 2 | 管理员登录 | POST `/api/auth/login` admin/Admin@2026!Secure | 返回token |
| 3 | JWT密钥来源 | 启动日志显示"配置文件(.jwt_secret)" | 固定密钥生效 |
| 4 | 角色初始化 | GET `/api/roles` | 4个预设角色 |
| 5 | 前端可访问 | 浏览器访问系统URL | 页面正常渲染 |
| 6 | 导入导出 | 下载模板+导出空数据 | Excel正常生成 |
| 7 | HTTPS | 浏览器HTTPS访问 | 证书有效+无混合内容 |
| 8 | 限流 | 短时间大量请求 | 超限返回429 |

---

## 11. 常见问题排查

| 问题 | 原因 | 解决方式 |
|------|------|---------|
| 启动报错"生产环境必须提供JWT密钥" | 未配置密钥 | 创建 `.jwt_secret` 文件或设置 `JWT_SECRET_KEY` 环境变量 |
| 登录返回401 | 密码错误 | 检查 `DEFAULT_ADMIN_PASSWORD` 环境变量 |
| 前端空白 | 静态文件路径错误 | 确认 `frontend/index.html` 存在 |
| CORS报错 | 来源不在白名单 | 设置 `CORS_ORIGINS` 环境变量 |
| 导入报错"日期格式" | Excel日期格式不对 | 确保日期列为 `YYYY-MM-DD` 格式 |
| 端口被占用 | 旧进程未停 | `kill`旧进程或改用 `--port` 指定其他端口 |
| 数据库锁定 | 多进程同时写 | SQLite单写模式，确保只有一个服务进程 |

---

## 12. 版本变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-12 | 基础CRUD + 7阶段门禁 |
| v2.0 | 2026-06-18 | RBAC权限 + 导入导出 + 报表 |
| v2.2.0 | 2026-06-26 | 审批工作流（6类型+手动审批人+故障降级+通知） |
| v2.3.0 | 2026-06-29 | 14项缺陷修复 |
| v3.0.0 | 2026-07-03 | 生产部署配置（JWT固定密钥+数据库重置+部署文档） |

---

*文档结束*
