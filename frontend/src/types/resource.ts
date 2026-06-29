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
