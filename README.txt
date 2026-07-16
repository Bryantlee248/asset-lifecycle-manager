"""独立前端页面 - 从后端API获取数据，通过内嵌脚本支持启动"""
# 这个文件仅用于文档说明，实际启动请使用 start.py

启动方式:
1. 确保 Python 环境已安装 fastapi, uvicorn, sqlalchemy, pydantic
2. 运行: python start.py
3. 打开浏览器访问 http://127.0.0.1:8000

系统功能:
- 7个管理页面: 数据总览、校验仪表盘、资产台账、采购入库、变更迁移、故障维修、维保续保、退役报废
- 13项自动校验: 编号空值、SN空值、位置空值、责任人空值、编号重复、位置重复、维保过期、维保到期、日期矛盾、报废无记录、孤儿记录、P1/P2未恢复
- 阶段门禁: 生命周期7阶段跳转必须满足前置条件
- 生命周期时间线: 点击资产行查看完整事件时间线
- 维保告警: 过期标红、30天内到期标黄
- P1/P2故障: 自动将主表阶段切换为维修

开发测试:
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_production_mvp.py tests/test_deployment_templates.py -q

服务器部署准备请阅读 deploy/README.md。公网 IP 的 HTTP 仅用于短期验证，正式对外使用前必须配置 HTTPS。
