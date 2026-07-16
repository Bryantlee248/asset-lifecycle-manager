"""一键启动脚本 - IT资产全生命周期管理系统（生产部署版）
用法:
  开发模式: python start.py
  生产模式: python start.py --production
  指定端口: python start.py --port 8000
  指定绑定: python start.py --host 0.0.0.0 --port 8000
"""
import sys
import os
import argparse

# 添加后端目录到路径
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

# 解析命令行参数
parser = argparse.ArgumentParser(description="IT资产全生命周期管理系统启动脚本")
parser.add_argument("--production", action="store_true", help="生产模式（设置ENV=production，启用JWT固定密钥）")
parser.add_argument("--host", default="127.0.0.1", help="绑定地址（默认127.0.0.1，生产环境建议0.0.0.0）")
parser.add_argument("--port", type=int, default=8000, help="监听端口（默认8000）")
args = parser.parse_args()

# 生产模式设置环境变量
if args.production:
    os.environ["ENV"] = "production"

from main import app
import uvicorn

from auth import DEFAULT_ADMIN_PASSWORD, JWT_SECRET_KEY

# 判断密钥来源
_jwt_source = "环境变量"
_jwt_secret_file = os.path.join(backend_dir, ".jwt_secret")
_jwt_dev_file = os.path.join(backend_dir, ".jwt_dev_key")
if os.environ.get("JWT_SECRET_KEY"):
    _jwt_source = "环境变量"
elif os.path.exists(_jwt_secret_file):
    _jwt_source = "配置文件(.jwt_secret)"
elif os.path.exists(_jwt_dev_file):
    _jwt_source = "开发随机(.jwt_dev_key)"

_env_label = "PRODUCTION" if args.production else "DEVELOPMENT"

print("=" * 60)
print("  IT资产全生命周期管理系统")
print("  长乐东南数据中心")
print("=" * 60)
print()
print(f"  运行模式: {_env_label}")
print(f"  启动地址: http://{args.host}:{args.port}")
print(f"  API文档:  http://{args.host}:{args.port}/docs")
print(f"  JWT密钥来源: {_jwt_source}")
print()
print(f"  默认管理员账号: admin / {DEFAULT_ADMIN_PASSWORD}")
print()
print("  按 Ctrl+C 停止服务")
print("=" * 60)

uvicorn.run(app, host=args.host, port=args.port)