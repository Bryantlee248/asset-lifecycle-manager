import {
  LayoutDashboard,
  ShieldCheck,
  Boxes,
  ShoppingCart,
  PackageCheck,
  PackageX,
  GitBranch,
  AlertTriangle,
  BadgeCheck,
  Trash2,
  CheckCircle2,
  Bell,
  Upload,
  BarChart3,
  LineChart,
  Users,
  UserCog,
  Settings,
  type LucideIcon,
} from 'lucide-vue-next'

export interface NavItem {
  key: string
  label: string
  path: string
  icon: LucideIcon
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: '指挥台',
    items: [
      { key: 'dashboard', label: '仪表盘', path: '/command-center/dashboard', icon: LayoutDashboard },
      { key: 'validation', label: '数据校验', path: '/command-center/validation', icon: ShieldCheck },
    ],
  },
  {
    title: '资产运营',
    items: [
      { key: 'assets', label: '资产台账', path: '/assets', icon: Boxes },
      { key: 'procurement', label: '采购管理', path: '/assets/procurement', icon: ShoppingCart },
      { key: 'inbound', label: '入库管理', path: '/assets/inbound', icon: PackageCheck },
      { key: 'outbound', label: '出库管理', path: '/assets/outbound', icon: PackageX },
      { key: 'changes', label: '变更管理', path: '/assets/changes', icon: GitBranch },
      { key: 'faults', label: '故障管理', path: '/assets/faults', icon: AlertTriangle },
      { key: 'warranties', label: '质保管理', path: '/assets/warranties', icon: BadgeCheck },
      { key: 'retirements', label: '退役管理', path: '/assets/retirements', icon: Trash2 },
    ],
  },
  {
    title: '协同中心',
    items: [
      { key: 'approval', label: '审批中心', path: '/collaboration/approval', icon: CheckCircle2 },
      { key: 'approvalNotify', label: '审批通知', path: '/collaboration/notifications', icon: Bell },
      { key: 'importExport', label: '导入导出', path: '/collaboration/import-export', icon: Upload },
    ],
  },
  {
    title: '洞察报告',
    items: [
      { key: 'reports', label: '报表中心', path: '/insights/reports', icon: BarChart3 },
      { key: 'stats', label: '统计分析', path: '/insights/stats', icon: LineChart },
    ],
  },
  {
    title: '系统治理',
    items: [
      { key: 'users', label: '用户管理', path: '/governance/users', icon: Users },
      { key: 'roles', label: '角色管理', path: '/governance/roles', icon: UserCog },
      { key: 'config', label: '系统配置', path: '/governance/config', icon: Settings },
    ],
  },
]

export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items)
