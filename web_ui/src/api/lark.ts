import http from './http'

export interface LarkBitable {
  id: string
  name: string
  app_token: string
  table_id: string
  mp_ids: string[]
  field_mapping: Record<string, string>
  enabled: boolean
  last_pushed_at: number | null
  last_error: string | null
  last_error_at: number | null
  created_at: string | null
  updated_at: string | null
}

export interface LarkBitableListResp {
  list: LarkBitable[]
  total: number
  page: { limit: number; offset: number }
  allowed_field_keys: string[]
}

export interface CreateBitableRequest {
  name: string
  app_token: string
  table_id: string
  mp_ids: string[]
  field_mapping: Record<string, string>
  enabled: boolean
}

export interface UpdateBitableRequest {
  name?: string
  app_token?: string
  table_id?: string
  mp_ids?: string[]
  field_mapping?: Record<string, string>
  enabled?: boolean
}

export interface LarkFieldInfo {
  name: string
  type: number
  id: string
}

export interface TestBitableResp {
  ok: boolean
  code?: number | null
  message?: string | null
  field_count?: number
  fields?: LarkFieldInfo[]
}

export interface LarkPushRecord {
  article_id: string
  bitable_id: string
  record_id: string | null
  pushed_at: number
}

export interface LarkPushListResp {
  list: LarkPushRecord[]
  total: number
  page: { limit: number; offset: number }
}

export const listBitables = (params?: { enabled?: boolean; mp_id?: string; limit?: number; offset?: number }) => {
  return http.get<LarkBitableListResp>('/wx/lark/bitables', { params })
}

export interface LarkStatus {
  enabled: boolean
  has_app_id: boolean
  has_app_secret: boolean
  bitable_count: number
  enabled_count: number
  token_ok: boolean | null
  issues: string[]
}

export const getLarkStatus = () => {
  return http.get<LarkStatus>('/wx/lark/status')
}

export const createBitable = (data: CreateBitableRequest) => {
  return http.post<LarkBitable>('/wx/lark/bitables', data)
}

export const getBitable = (id: string) => {
  return http.get<LarkBitable>(`/wx/lark/bitables/${id}`)
}

export const updateBitable = (id: string, data: UpdateBitableRequest) => {
  return http.put<LarkBitable>(`/wx/lark/bitables/${id}`, data)
}

export const deleteBitable = (id: string) => {
  return http.delete(`/wx/lark/bitables/${id}`)
}

export const testBitable = (id: string) => {
  return http.post<TestBitableResp>(`/wx/lark/bitables/${id}/test`)
}

export const manualPush = (id: string, article_id: string) => {
  return http.post<{ submitted: boolean; already_pushed: boolean; previous_record_id: string | null }>(
    `/wx/lark/bitables/${id}/push`,
    { article_id },
  )
}

export const listPushes = (params?: { article_id?: string; bitable_id?: string; limit?: number; offset?: number }) => {
  return http.get<LarkPushListResp>('/wx/lark/pushes', { params })
}