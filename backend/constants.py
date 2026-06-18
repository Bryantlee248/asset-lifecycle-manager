"""统一下拉选项配置 - 消除 main.py 和 import_export_reports.py 中的重复定义"""

CATEGORIES = ["服务器", "网络设备", "存储设备", "安全设备", "UPS", "配电设备", "空调", "KVM", "PDU", "其他"]
LIFECYCLE_STAGES = ["规划", "在途", "上架", "运行", "维修", "待报废", "已报废"]
WARRANTY_STATUSES = ["在保", "过保", "续保中", "无维保"]
INSPECTION_RESULTS = ["合格", "不合格", "待验收"]
CHANGE_TYPES = ["位置变更", "配置变更", "归属变更", "IP变更", "其他"]
FAULT_LEVELS = ["P1", "P2", "P3", "P4"]
HANDLE_METHODS = ["现场修复", "远程修复", "返厂维修", "更换设备", "重启恢复", "其他"]
ROOT_CAUSES = ["硬件故障", "软件故障", "人为误操作", "环境因素", "供应商问题", "老化损耗", "其他"]
RENEWAL_DECISIONS = ["续保", "过保运行", "计划报废", "评估中"]
RETIRE_CATEGORIES = ["正常报废", "损坏报废", "技术淘汰", "其他"]
DATA_CLEAR_OPTIONS = ["已清除", "未清除", "不适用"]
COMPLETION_STATUSES = ["进行中", "已完成", "已取消"]
