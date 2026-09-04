import http from './http'

export interface RedfoxLogEntry {
  endpoint: string
  code: number
  success: boolean
  latency_ms: number
  mp_id: string
  request: Record<string, any>
  error_msg: string
  http_status: number
  timestamp: string
}

export interface RedfoxStats {
  date: string
  total: number
  success: number
  failed: number
  endpoints: Record<string, string>
  mp_stats: Record<string, string>
  recent_logs: RedfoxLogEntry[]
}

export interface RedfoxLogsResponse {
  items: RedfoxLogEntry[]
  limit: number
  offset: number
}

export interface RedfoxClearResponse {
  cleared_at: string
}

/**
 * 获取 redfox 调用统计
 */
export const getRedfoxStats = async (date?: string): Promise<RedfoxStats> => {
  try {
    const params = date ? { date } : {}
    const response = await http.get('wx/redfox/stats', { params })
    const data = response || {}
    return {
      date: data.date || new Date().toISOString().split('T')[0],
      total: data.total || 0,
      success: data.success || 0,
      failed: data.failed || 0,
      endpoints: data.endpoints || {},
      mp_stats: data.mp_stats || {},
      recent_logs: data.recent_logs || []
    }
  } catch (error) {
    console.error('获取 redfox 统计失败:', error)
    return {
      date: date || new Date().toISOString().split('T')[0],
      total: 0,
      success: 0,
      failed: 0,
      endpoints: {},
      mp_stats: {},
      recent_logs: []
    }
  }
}

/**
 * 获取 redfox 调用日志
 */
export const getRedfoxLogs = async (
  limit = 50,
  offset = 0
): Promise<RedfoxLogsResponse> => {
  try {
    const response = await http.get('wx/redfox/logs', {
      params: { limit, offset }
    })
    return {
      items: response?.items || [],
      limit: response?.limit || limit,
      offset: response?.offset || offset
    }
  } catch (error) {
    console.error('获取 redfox 日志失败:', error)
    return { items: [], limit, offset }
  }
}

/**
 * 清空 redfox 调用日志
 */
export const clearRedfoxLogs = async (): Promise<RedfoxClearResponse | null> => {
  try {
    const response = await http.post('wx/redfox/logs/clear')
    return response || null
  } catch (error) {
    console.error('清空 redfox 日志失败:', error)
    return null
  }
}
