<template>
  <div class="redfox-logs">
    <a-page-header title="Redfox 接口日志" subtitle="redfox 数据接口调用日志与统计">
      <a-card :bordered="false" class="stats-card">
        <a-space>
          <a-date-picker
            v-model="selectedDate"
            style="width: 200px"
            @change="handleDateChange"
            :disabled-date="disabledDate"
            allow-clear
          />
          <a-button type="primary" @click="loadStats" :loading="loading">
            <template #icon><icon-search /></template>
            查询
          </a-button>
          <a-button @click="loadToday" :loading="loading">
            <template #icon><icon-calendar /></template>
            今日统计
          </a-button>
          <a-button @click="refresh" :loading="loading">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
          <a-popconfirm
            content="确认清空所有 redfox 调用日志？历史日期统计不受影响。"
            @ok="handleClear"
          >
            <a-button status="danger" :loading="clearing">
              <template #icon><icon-delete /></template>
              清空日志
            </a-button>
          </a-popconfirm>
        </a-space>
      </a-card>

      <a-spin :loading="loading" style="width: 100%">
        <!-- 概览 -->
        <a-card :bordered="false" class="stats-card" title="调用概览">
          <a-row :gutter="16">
            <a-col :xs="24" :sm="12" :md="6">
              <a-statistic title="调用总数" :value="stats.total">
                <template #prefix><icon-send /></template>
              </a-statistic>
            </a-col>
            <a-col :xs="24" :sm="12" :md="6">
              <a-statistic
                title="成功"
                :value="stats.success"
                :value-style="{ color: '#00b42a' }"
              >
                <template #prefix><icon-check-circle-fill /></template>
              </a-statistic>
            </a-col>
            <a-col :xs="24" :sm="12" :md="6">
              <a-statistic
                title="失败"
                :value="stats.failed"
                :value-style="stats.failed > 0 ? { color: '#f53f3f' } : {}"
              >
                <template #prefix><icon-close-circle-fill /></template>
              </a-statistic>
            </a-col>
            <a-col :xs="24" :sm="12" :md="6">
              <a-statistic
                title="成功率"
                :value="successRateText"
                :value-style="{ color: '#165dff' }"
              >
                <template #prefix><icon-star /></template>
              </a-statistic>
            </a-col>
          </a-row>
        </a-card>

        <!-- 接口维度 -->
        <a-card
          :bordered="false"
          class="stats-card"
          title="接口维度统计"
          v-if="Object.keys(stats.endpoints || {}).length > 0"
        >
          <a-table
            :columns="endpointColumns"
            :data="endpointTableData"
            :pagination="false"
            :stripe="true"
            size="small"
          >
            <template #count="{ record }">
              <a-tag :color="record.count > 50 ? 'red' : record.count > 10 ? 'orange' : 'blue'">
                {{ record.count }}
              </a-tag>
            </template>
          </a-table>
        </a-card>

        <!-- 公众号维度 -->
        <a-card
          :bordered="false"
          class="stats-card"
          title="公众号维度统计"
          v-if="Object.keys(stats.mp_stats || {}).length > 0"
        >
          <a-table
            :columns="mpColumns"
            :data="mpTableData"
            :pagination="{ pageSize: 10 }"
            :stripe="true"
            size="small"
          >
            <template #count="{ record }">
              <a-tag :color="record.count > 50 ? 'red' : record.count > 10 ? 'orange' : 'arcoblue'">
                {{ record.count }}
              </a-tag>
            </template>
          </a-table>
        </a-card>

        <!-- 调用日志 -->
        <a-card :bordered="false" class="stats-card" title="最近调用日志">
          <a-table
            :columns="logColumns"
            :data="logs"
            :pagination="{ pageSize: 20, showTotal: true }"
            :stripe="true"
            size="small"
          >
            <template #success="{ record }">
              <a-tag :color="record.success ? 'green' : 'red'">
                {{ record.success ? '成功' : '失败' }}
              </a-tag>
            </template>
            <template #endpoint="{ record }">
              <a-tag>{{ record.endpoint }}</a-tag>
            </template>
            <template #latency="{ record }">
              <span :style="{ color: record.latency_ms > 3000 ? '#f53f3f' : record.latency_ms > 1000 ? '#ff7d00' : '#00b42a' }">
                {{ record.latency_ms }} ms
              </span>
            </template>
            <template #code="{ record }">
              <a-tag v-if="record.code === 2000" color="green">{{ record.code }}</a-tag>
              <a-tag v-else color="red">{{ record.code }}</a-tag>
            </template>
            <template #request="{ record }">
              <a-tooltip :content="JSON.stringify(record.request, null, 2)">
                <span class="request-cell">
                  {{ formatRequest(record.request) }}
                </span>
              </a-tooltip>
            </template>
            <template #error_msg="{ record }">
              <span v-if="record.error_msg" class="error-cell">{{ record.error_msg }}</span>
              <span v-else class="muted">—</span>
            </template>
          </a-table>
        </a-card>
      </a-spin>
    </a-page-header>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  IconSearch,
  IconCalendar,
  IconRefresh,
  IconSend,
  IconCheckCircleFill,
  IconCloseCircleFill,
  IconStar,
  IconDelete,
} from '@arco-design/web-vue/es/icon'
import {
  clearRedfoxLogs,
  getRedfoxLogs,
  getRedfoxStats,
  type RedfoxLogEntry,
  type RedfoxStats,
} from '@/api/redfox'

const loading = ref(false)
const clearing = ref(false)
const selectedDate = ref<string>('')
const stats = ref<RedfoxStats>({
  date: '',
  total: 0,
  success: 0,
  failed: 0,
  endpoints: {},
  mp_stats: {},
  recent_logs: [],
})
const logs = ref<RedfoxLogEntry[]>([])

const endpointColumns = [
  { title: '接口', dataIndex: 'endpoint', width: '60%' },
  { title: '次数', dataIndex: 'count', slotName: 'count', width: '20%' },
  { title: '占比', dataIndex: 'percentage', width: '20%' },
]

const mpColumns = [
  { title: '公众号', dataIndex: 'mp_id', width: '40%', ellipsis: true },
  { title: '次数', dataIndex: 'count', slotName: 'count', width: '20%' },
  { title: '占比', dataIndex: 'percentage', width: '20%' },
]

const logColumns = [
  { title: '时间', dataIndex: 'timestamp', width: '160px' },
  { title: '接口', dataIndex: 'endpoint', slotName: 'endpoint', width: '220px' },
  { title: '结果', dataIndex: 'success', slotName: 'success', width: '80px' },
  { title: 'code', dataIndex: 'code', slotName: 'code', width: '70px' },
  { title: 'HTTP', dataIndex: 'http_status', width: '70px' },
  { title: '耗时', dataIndex: 'latency_ms', slotName: 'latency', width: '90px' },
  { title: '公众号', dataIndex: 'mp_id', width: '200px', ellipsis: true },
  { title: '请求', dataIndex: 'request', slotName: 'request' },
  { title: '错误信息', dataIndex: 'error_msg', slotName: 'error_msg', width: '240px' },
]

const successRateText = computed(() => {
  const total = stats.value.total || 0
  if (!total) return '0%'
  return ((stats.value.success / total) * 100).toFixed(2) + '%'
})

const endpointTableData = computed(() => {
  const data: any[] = []
  Object.entries(stats.value.endpoints || {}).forEach(([endpoint, count]) => {
    const c = parseInt(count) || 0
    data.push({
      endpoint,
      count: c,
      percentage: stats.value.total > 0
        ? ((c / stats.value.total) * 100).toFixed(2) + '%'
        : '0%',
    })
  })
  return data.sort((a, b) => b.count - a.count)
})

const mpTableData = computed(() => {
  const data: any[] = []
  Object.entries(stats.value.mp_stats || {}).forEach(([mpId, count]) => {
    const c = parseInt(count) || 0
    data.push({
      mp_id: mpId,
      count: c,
      percentage: stats.value.total > 0
        ? ((c / stats.value.total) * 100).toFixed(2) + '%'
        : '0%',
    })
  })
  return data.sort((a, b) => b.count - a.count)
})

const disabledDate = (current: Date) => current && current > new Date()

const formatRequest = (request: Record<string, any> | undefined) => {
  if (!request || Object.keys(request).length === 0) return '—'
  return Object.entries(request)
    .map(([k, v]) => `${k}=${v}`)
    .join(', ')
}

const handleDateChange = (value: string) => {
  selectedDate.value = value || ''
}

const loadLogs = async () => {
  try {
    const res = await getRedfoxLogs(200, 0)
    logs.value = res.items || []
  } catch (err: any) {
    console.error('加载 redfox 日志失败', err)
  }
}

const loadStats = async () => {
  loading.value = true
  try {
    const date = selectedDate.value || new Date().toISOString().split('T')[0]
    const result = await getRedfoxStats(date)
    stats.value = {
      date: result.date || date,
      total: result.total || 0,
      success: result.success || 0,
      failed: result.failed || 0,
      endpoints: result.endpoints || {},
      mp_stats: result.mp_stats || {},
      recent_logs: result.recent_logs || [],
    }
    if (stats.value.total === 0) {
      Message.info('该日期暂无 redfox 调用记录')
    }
  } catch (err: any) {
    Message.error(err?.message || '加载统计失败')
  } finally {
    loading.value = false
  }
}

const loadToday = async () => {
  selectedDate.value = ''
  await loadStats()
}

const refresh = async () => {
  await Promise.all([loadStats(), loadLogs()])
}

const handleClear = async () => {
  clearing.value = true
  try {
    const res = await clearRedfoxLogs()
    if (res) {
      Message.success('已清空 redfox 调用日志')
      await refresh()
    } else {
      Message.error('清空失败')
    }
  } catch (err: any) {
    Message.error(err?.message || '清空失败')
  } finally {
    clearing.value = false
  }
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.redfox-logs {
  padding: 16px;
}

.stats-card {
  margin-bottom: 16px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}

.stats-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

:deep(.arco-statistic-title) {
  font-size: 14px;
  margin-bottom: 8px;
}

:deep(.arco-statistic-content) {
  font-size: 24px;
}

:deep(.arco-table-wrapper) {
  margin-top: -8px;
}

.request-cell {
  display: inline-block;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.error-cell {
  color: #f53f3f;
  font-size: 12px;
}

.muted {
  color: #c9cdd4;
}
</style>
