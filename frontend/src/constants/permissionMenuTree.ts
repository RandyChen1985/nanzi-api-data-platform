export interface PermissionMenuChild {
  id: string
  label: string
}

export interface PermissionMenuNode {
  id: string
  label: string
  children: PermissionMenuChild[]
}

/** 管理后台权限配置用菜单树（用户/角色权限编辑共用） */
export const PERMISSION_MENU_TREE: PermissionMenuNode[] = [
  {
    id: 'menu:overview',
    label: '系统概览',
    children: [{ id: 'element:overview:stats', label: '查看全量系统统计' }],
  },
  {
    id: 'menu:asset-panorama',
    label: '数据资产全景',
    children: [],
  },
  {
    id: 'menu:catalog:requests',
    label: '目录权限申请',
    children: [
      { id: 'element:catalog:review', label: '审批目录访问申请' },
      { id: 'element:catalog:manage', label: '编辑数据产品信息' },
    ],
  },
  {
    id: 'menu:lab',
    label: 'SQL 实验室',
    children: [
      { id: 'element:lab:generate', label: 'AI 生成/修改 SQL' },
      { id: 'element:lab:publish', label: '发布为 API' },
      { id: 'element:lab:export', label: 'Excel 数据导出' },
      { id: 'element:lab:analysis', label: 'AI 多轮分析/图表' },
      { id: 'element:lab:mode_api', label: '模式：API 调试' },
      { id: 'element:lab:mode_analyst', label: '模式：自助取数' },
    ],
  },
  {
    id: 'menu:resources',
    label: '接口管理',
    children: [
      { id: 'element:resource:create', label: '新建接口' },
      { id: 'element:resource:edit', label: '编辑接口' },
      { id: 'element:resource:delete', label: '删除接口' },
      { id: 'element:resource:import', label: '导入配置' },
      { id: 'element:resource:export', label: '导出配置' },
      { id: 'element:resource:manage_special', label: '管理特殊资源(TTL/SQL测试)' },
      { id: 'element:catalog:publish', label: '发布到产品目录' },
    ],
  },
  {
    id: 'menu:metadata',
    label: '元数据管理',
    children: [
      { id: 'element:metadata:view', label: '查看：元数据详情' },
      { id: 'element:metadata:manage', label: '管理：编辑元数据/指标' },
    ],
  },
  {
    id: 'menu:datasource',
    label: '数据源管理',
    children: [{ id: 'element:datasource:edit', label: '编辑数据源' }],
  },
  {
    id: 'menu:audit',
    label: '审计日志',
    children: [
      { id: 'element:audit:export', label: '导出审计日志' },
      { id: 'element:audit:manage', label: '管理所有用户日志' },
    ],
  },
  {
    id: 'menu:playground',
    label: 'API 调试',
    children: [],
  },
  {
    id: 'menu:users',
    label: '用户管理',
    children: [{ id: 'element:user:manage', label: '管理用户/权限' }],
  },
  {
    id: 'menu:system:roles',
    label: '角色管理',
    children: [],
  },
  {
    id: 'menu:config',
    label: '系统设置',
    children: [{ id: 'element:config:save', label: '保存系统配置' }],
  },
]

export function findMenuNode(menuId: string): PermissionMenuNode | undefined {
  return PERMISSION_MENU_TREE.find((m) => m.id === menuId)
}

export function getMenuChildIds(menuId: string): string[] {
  return findMenuNode(menuId)?.children.map((c) => c.id) ?? []
}
