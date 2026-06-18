"""一键启动脚本 - IT资产全生命周期管理系统"""
import sys
import os

# 添加后端目录到路径
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from main import app
import uvicorn

print("=" * 60)
print("  IT资产全生命周期管理系统")
print("  长乐东南数据中心")
print("=" * 60)
print()
print("  启动地址: http://127.0.0.1:8000")
print("  API文档:  http://127.0.0.1:8000/docs")
print()
print("  默认管理员账号: admin / admin123")
print()
print("  按 Ctrl+C 停止服务")
print("=" * 60)

uvicorn.run(app, host="127.0.0.1", port=8000)