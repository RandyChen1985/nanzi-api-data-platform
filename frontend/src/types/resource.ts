export interface Resource {
  resource_key: string
  resource_name: string
  resource_group?: string
  data_source: string
  resource_mode: string
  created_at?: string
  updated_at?: string
  status: number
  reference_count?: number
  remarks?: string
  cache_ttl?: number
  custom_sql?: string
  fields_config?: unknown[]
  allowed_filters?: unknown[]
}

/** 系统内置资源专用分组名（数据库迁移与 meta_service 硬编码使用） */
export const SYSTEM_RESOURCE_GROUP = 'System'

/** 列表中按系统内置锁定（状态不可改、模式展示为「系统」），DB 中 resource_mode 可能仍为 SQL */
export const LOCKED_SYSTEM_RESOURCE_KEYS = new Set(['system.metadata.search'])

export function isLockedSystemResource(resource: {
  resource_key: string
  resource_mode?: string
}): boolean {
  return resource.resource_mode === 'SYSTEM' || LOCKED_SYSTEM_RESOURCE_KEYS.has(resource.resource_key)
}

export function displayResourceMode(resource: {
  resource_key: string
  resource_mode: string
}): string {
  return isLockedSystemResource(resource) ? 'SYSTEM' : resource.resource_mode
}

/** system.sql.execute 使用 TTL/SQL 测试 + 更多菜单；system.metadata.search 仅保留调试 */
export type SystemResourceActionKind = 'sql_execute' | 'metadata_search_debug_only'

export function getSystemResourceActionKind(resourceKey: string): SystemResourceActionKind | null {
  if (resourceKey === 'system.sql.execute') return 'sql_execute'
  if (resourceKey === 'system.metadata.search') return 'metadata_search_debug_only'
  return null
}

export interface ResourceGroupTab {
  name: string
  label: string
  count: number
  isSystem?: boolean
}

export function isSystemResourceGroup(name?: string | null): boolean {
  return (name || '').trim().toLowerCase() === SYSTEM_RESOURCE_GROUP.toLowerCase()
}

export function sortResourceGroups(groups: string[]): string[] {
  return [...groups].sort((a, b) => {
    if (isSystemResourceGroup(a)) return -1
    if (isSystemResourceGroup(b)) return 1
    return a.localeCompare(b, 'zh-CN')
  })
}

export interface AccessLog {
  id: number
  trace_id: string
  user_name: string
  method: string
  endpoint: string
  status_code: number
  process_time_ms: number
  client_ip: string
  created_at: string
  request_params?: string
}

export type ResourceSortField = 'updated_at' | 'resource_name' | 'status' | 'resource_mode'
