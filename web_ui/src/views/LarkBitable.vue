<script setup lang="ts">
import { ref, reactive, onMounted, computed, h, nextTick } from 'vue'
import {
  listBitables,
  createBitable,
  updateBitable,
  deleteBitable,
  testBitable,
  listPushes,
  manualPush,
  getLarkStatus,
} from '@/api/lark'
import type {
  LarkBitable,
  CreateBitableRequest,
  UpdateBitableRequest,
  TestBitableResp,
  LarkPushRecord,
  LarkStatus,
} from '@/api/lark'
import { Modal, Message } from '@arco-design/web-vue'
import {
  IconPlus,
  IconRefresh,
  IconEdit,
  IconDelete,
  IconLink,
  IconCheckCircle,
  IconCloseCircle,
  IconStorage,
} from '@arco-design/web-vue/es/icon'
import MpMultiSelect from '@/components/MpMultiSelect.vue'
import type { MpItem } from '@/types/subscription'

interface MappingRow {
  key: string
  value: string
}

const bitables = ref<LarkBitable[]>([])
const pushes = ref<LarkPushRecord[]>([])
const allowedKeys = ref<string[]>([])
const total = ref(0)
const loading = ref(false)
const pushesLoading = ref(false)
const larkStatus = ref<LarkStatus | null>(null)

const showForm = ref(false)
const showTestModal = ref(false)
const showMpSelector = ref(false)
const editingId = ref<string | null>(null)
const mpSelectorRef = ref<InstanceType<typeof MpMultiSelect> | null>(null)
const formData = reactive<{
  name: string
  app_token: string
  table_id: string
  selected_mps: MpItem[]
  mapping_rows: MappingRow[]
  enabled: boolean
}>({
  name: '',
  app_token: '',
  table_id: '',
  selected_mps: [],
  mapping_rows: [{ key: '', value: '' }],
  enabled: true,
})

const testResult = ref<TestBitableResp | null>(null)
const testing = ref(false)
const submitting = ref(false)

// ---------- 列表 ----------

const loadBitables = async () => {
  loading.value = true
  try {
    const resp = await listBitables({ limit: 200 })
    bitables.value = resp.list || []
    total.value = resp.total || 0
    allowedKeys.value = resp.allowed_field_keys || []
  } catch (err: any) {
    Message.error('加载失败: ' + (err?.message || String(err)))
  } finally {
    loading.value = false
  }
}

const loadStatus = async () => {
  try {
    larkStatus.value = await getLarkStatus()
  } catch (err: any) {
    console.error('loadStatus failed:', err)
    larkStatus.value = null
  }
}

const loadPushes = async () => {
  pushesLoading.value = true
  try {
    const resp = await listPushes({ limit: 20 })
    pushes.value = resp.list || []
  } catch (err: any) {
    console.error('加载推送历史失败', err)
  } finally {
    pushesLoading.value = false
  }
}

onMounted(() => {
  loadStatus()
  loadBitables()
  loadPushes()
})

const columns = [
  { title: '状态', slotName: 'enabled', width: 80 },
  { title: '名称', slotName: 'name', width: 200 },
  { title: 'App Token', dataIndex: 'app_token', width: 200, ellipsis: true, tooltip: true },
  { title: 'Table ID', dataIndex: 'table_id', width: 200, ellipsis: true, tooltip: true },
  { title: '关联公众号', slotName: 'mp_ids', width: 80 },
  { title: '最近推送', slotName: 'last_pushed', width: 200 },
  { title: '操作', slotName: 'action', width: 200, fixed: 'right' },
]

const pushColumns = [
  { title: '推送时间', slotName: 'pushed_at', width: 180 },
  { title: '文章 ID', dataIndex: 'article_id', ellipsis: true, tooltip: true },
  { title: 'Bitable ID', dataIndex: 'bitable_id', ellipsis: true, tooltip: true },
  { title: '飞书记录 ID', dataIndex: 'record_id', ellipsis: true, tooltip: true },
]

const formatTime = (ts: number | null | undefined): string => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString()
}

// ---------- 表单 ----------

const resetForm = () => {
  formData.name = ''
  formData.app_token = ''
  formData.table_id = ''
  formData.selected_mps = []
  formData.mapping_rows = [{ key: '', value: '' }]
  formData.enabled = true
  editingId.value = null
}

const showCreate = () => {
  resetForm()
  showForm.value = true
}

const showEdit = async (b: LarkBitable) => {
  resetForm()
  editingId.value = b.id
  formData.name = b.name
  formData.app_token = b.app_token
  formData.table_id = b.table_id
  formData.enabled = !!b.enabled
  // 把后端存的 mp_ids 字符串数组转成 MpItem[] 占位,
  // 打开选择器后 MpMultiSelect.parseSelected 会尝试用搜索结果补全 mp_name/cover。
  formData.selected_mps = (b.mp_ids || []).map((id) => ({
    id,
    mp_name: id,
    mp_cover: '',
  }))
  const entries = Object.entries(b.field_mapping || {})
  formData.mapping_rows = entries.length
    ? entries.map(([k, v]) => ({ key: k, value: v }))
    : [{ key: '', value: '' }]
  showForm.value = true
}

const addMappingRow = () => {
  formData.mapping_rows.push({ key: '', value: '' })
}

const removeMappingRow = (idx: number) => {
  if (formData.mapping_rows.length === 1) {
    formData.mapping_rows[0] = { key: '', value: '' }
    return
  }
  formData.mapping_rows.splice(idx, 1)
}

const collectPayload = (): CreateBitableRequest | UpdateBitableRequest => {
  if (!formData.name.trim()) throw new Error('请输入名称')
  if (!formData.app_token.trim()) throw new Error('请输入 App Token')
  if (!formData.table_id.trim()) throw new Error('请输入 Table ID')

  const dedup = Array.from(
    new Set(formData.selected_mps.map((m) => m.id).filter(Boolean)),
  )

  const field_mapping: Record<string, string> = {}
  const seen = new Set<string>()
  for (const row of formData.mapping_rows) {
    const k = (row.key || '').trim()
    const v = (row.value || '').trim()
    if (!k && !v) continue
    if (!k) throw new Error('字段映射: 选择文章字段后必须填写多维表字段名')
    if (!v) throw new Error(`字段映射 [${k}]: 多维表字段名不能为空`)
    if (seen.has(k)) throw new Error(`字段映射存在重复: ${k}`)
    seen.add(k)
    field_mapping[k] = v
  }

  return {
    name: formData.name.trim(),
    app_token: formData.app_token.trim(),
    table_id: formData.table_id.trim(),
    mp_ids: dedup,
    field_mapping,
    enabled: formData.enabled,
  }
}

const submitForm = async () => {
  let payload
  try {
    payload = collectPayload()
  } catch (e: any) {
    Message.warning(e?.message || String(e))
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      await updateBitable(editingId.value, payload)
      Message.success('已更新')
    } else {
      await createBitable(payload as CreateBitableRequest)
      Message.success('已创建')
    }
    showForm.value = false
    await loadBitables()
  } catch (err: any) {
    Message.error('保存失败: ' + (err?.message || String(err)))
  } finally {
    submitting.value = false
  }
}

const openMpSelector = async () => {
  showMpSelector.value = true
  // 等 MpMultiSelect 的 onMounted 拉完一次 searchMps 后,
  // 用 parseSelected 把 selected_mps 占位项尝试用搜索结果回填 mp_name/cover。
  await nextTick()
  await new Promise((r) => setTimeout(r, 400))
  if (mpSelectorRef.value && formData.selected_mps.length) {
    mpSelectorRef.value.parseSelected(formData.selected_mps)
  }
}

// ---------- 测试 / 删除 / 手动推送 ----------

const onTest = async (b: LarkBitable) => {
  testing.value = true
  testResult.value = null
  showTestModal.value = true
  try {
    const resp = await testBitable(b.id)
    testResult.value = resp
    if (resp?.ok) {
      Message.success(`连通正常,共 ${resp.field_count ?? 0} 个字段`)
      await loadBitables()
    } else {
      Message.warning('连通失败: ' + (resp?.message || '未知错误'))
    }
  } catch (err: any) {
    testResult.value = { ok: false, message: err?.message || String(err) }
    Message.error('测试失败: ' + (err?.message || String(err)))
  } finally {
    testing.value = false
  }
}

const onDelete = (b: LarkBitable) => {
  Modal.confirm({
    title: '确认删除',
    content: `删除多维表配置「${b.name}」?推送历史会保留。`,
    okText: '删除',
    cancelText: '取消',
    okButtonProps: { status: 'danger' },
    onOk: async () => {
      try {
        await deleteBitable(b.id)
        Message.success('已删除')
        await loadBitables()
      } catch (err: any) {
        Message.error('删除失败: ' + (err?.message || String(err)))
      }
    },
  })
}

const onManualPush = (b: LarkBitable) => {
  let articleId = ''
  Modal.confirm({
    title: '手动推送文章',
    content: () =>
      h('div', [
        h('p', { style: 'margin-top:0;' }, `推送到「${b.name}」`),
        h(
          'a-input',
          {
            placeholder: '输入 article_id',
            'allow-clear': true,
            onInput: (v: string) => {
              articleId = v
            },
          },
        ),
      ]),
    okText: '提交',
    cancelText: '取消',
    onOk: async () => {
      if (!articleId.trim()) {
        Message.warning('请输入 article_id')
        return Promise.reject()
      }
      try {
        const resp = await manualPush(b.id, articleId.trim())
        const tag = resp?.already_pushed ? '(已存在 record_id)' : '(新推送)'
        Message.success(`已提交到 worker ${tag}`)
      } catch (err: any) {
        Message.error('提交失败: ' + (err?.message || String(err)))
      }
    },
  })
}

// arco Modal.confirm 中用 h() 需要显式 import (setup 内置 h)
// 实际可在 <script setup> 中直接使用 h — Vue 3 内置

const sortedBitables = computed(() => bitables.value)

const statusIssues = computed(() => larkStatus.value?.issues || [])
const statusEnabled = computed(() => larkStatus.value?.enabled ?? false)
</script>

<template>
  <div class="lark-page">
    <a-card title="飞书多维表配置" :bordered="false">
      <template #extra>
        <a-space>
          <a-button @click="loadBitables">
            <template #icon><icon-refresh /></template>
            刷新
          </a-button>
          <a-button type="primary" @click="showCreate">
            <template #icon><icon-plus /></template>
            新建配置
          </a-button>
        </a-space>
      </template>

      <a-alert
        v-if="!allowedKeys.length"
        type="warning"
        style="margin-bottom: 12px"
        :show-icon="true"
      >
        后端尚未返回允许的字段列表,请检查后端是否正常。
      </a-alert>

      <a-alert
        v-if="statusIssues.length"
        :type="statusEnabled ? 'warning' : 'error'"
        style="margin-bottom: 12px"
        :show-icon="true"
        :title="statusEnabled ? '推送可能不生效' : '推送未启用'"
      >
        <ul style="margin: 0; padding-left: 18px">
          <li v-for="(msg, i) in statusIssues" :key="i">{{ msg }}</li>
        </ul>
      </a-alert>

      <p style="margin: 0 0 12px; color: var(--color-text-3); font-size: 12px">
        允许的文章字段 (LHS): <code>{{ allowedKeys.join(', ') || '—' }}</code>
      </p>

      <a-table
        :columns="columns"
        :data="sortedBitables"
        :loading="loading"
        :pagination="false"
        row-key="id"
        size="small"
      >
        <template #enabled="{ record }">
          <a-tag v-if="record.enabled" color="green">启用</a-tag>
          <a-tag v-else color="gray">禁用</a-tag>
        </template>
        <template #name="{ record }">
          <strong>{{ record.name }}</strong>
          <div style="font-size: 11px; color: var(--color-text-3)">{{ record.id }}</div>
        </template>
        <template #mp_ids="{ record }">
          <a-tag color="arcoblue" style="margin: 1px">
            {{ record.mp_ids?.length }}
          </a-tag>
        </template>
        <template #field_mapping="{ record }">
          <a-tag
            v-for="(v, k) in record.field_mapping"
            :key="k"
            color="gray"
            style="margin: 1px; font-family: var(--code-font-family)"
          >
            {{ k }} → {{ v }}
          </a-tag>
          <span
            v-if="!Object.keys(record.field_mapping || {}).length"
            style="color: var(--color-text-3)"
          >(无映射)</span>
        </template>
        <template #last_pushed="{ record }">
          <div>{{ formatTime(record.last_pushed_at) }}</div>
          <div
            v-if="record.last_error"
            style="font-size: 11px; color: rgb(var(--red-6)); max-width: 360px; word-break: break-all"
          >
            {{ formatTime(record.last_error_at) }}: {{ record.last_error }}
          </div>
        </template>
        <template #action="{ record }">
          <a-space>
            <a-button size="mini" @click="onTest(record)">
              <template #icon><icon-link /></template>
              测试
            </a-button>
            <a-button size="mini" @click="onManualPush(record)" type="outline">
              <template #icon><icon-storage /></template>
              推送
            </a-button>
            <a-button size="mini" @click="showEdit(record)" type="secondary">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-button size="mini" @click="onDelete(record)" status="danger" type="outline">
              <template #icon><icon-delete /></template>
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>

      <div style="margin-top: 12px; color: var(--color-text-3); font-size: 12px">
        共 {{ total }} 条
      </div>
    </a-card>

    <a-card title="最近推送 (20 条)" :bordered="false" style="margin-top: 16px">
      <a-table
        :columns="pushColumns"
        :data="pushes"
        :loading="pushesLoading"
        :pagination="false"
        row-key="article_id"
        size="small"
      >
        <template #pushed_at="{ record }">
          {{ formatTime(record.pushed_at) }}
        </template>
      </a-table>
    </a-card>

    <!-- 表单模态 -->
    <a-modal
      v-model:visible="showForm"
      :title="editingId ? '编辑多维表配置' : '新建多维表配置'"
      :ok-text="editingId ? '保存' : '创建'"
      :ok-button-props="{ loading: submitting }"
      :width="720"
      @ok="submitForm"
      unmount-on-close
    >
      <a-form :model="formData" layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model="formData.name" placeholder="例:科技日报 → 飞书多维表" max-length="255" />
        </a-form-item>
        <a-form-item label="App Token" required>
          <a-input v-model="formData.app_token" placeholder="bascnxxxxxxxxxxxxxxxxxxxxxx" />
        </a-form-item>
        <a-form-item label="Table ID" required>
          <a-input v-model="formData.table_id" placeholder="tblxxxxxxxxxxxx" />
        </a-form-item>
        <a-form-item label="关联公众号">
          <a-input
            :model-value="`已选 ${formData.selected_mps.length} 个公众号`"
            placeholder="留空则对所有公众号生效"
            readonly
            allow-clear
          >
            <template #append>
              <a-button @click="openMpSelector">选择</a-button>
            </template>
          </a-input>
        </a-form-item>
        <a-form-item>
          <a-checkbox v-model="formData.enabled">启用此配置</a-checkbox>
        </a-form-item>

        <a-divider>字段映射</a-divider>
        <p style="margin: 0 0 8px; color: var(--color-text-3); font-size: 12px">
          左侧 = 文章字段; 右侧 = 多维表字段名
        </p>
        <div
          v-for="(row, idx) in formData.mapping_rows"
          :key="idx"
          style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center"
        >
          <a-select
            v-model="row.key"
            placeholder="选择文章字段"
            style="flex: 1"
            allow-clear
          >
            <a-option v-for="k in allowedKeys" :key="k" :value="k">{{ k }}</a-option>
          </a-select>
          <a-input
            v-model="row.value"
            placeholder="多维表字段名"
            style="flex: 1"
            allow-clear
          />
          <a-button
            size="mini"
            status="danger"
            type="outline"
            @click="removeMappingRow(idx)"
          >
            删除
          </a-button>
        </div>
        <a-button size="small" type="dashed" @click="addMappingRow">
          + 添加一行
        </a-button>
      </a-form>
    </a-modal>

    <!-- 测试结果模态 -->
    <a-modal
      v-model:visible="showTestModal"
      title="连通测试结果"
      :footer="false"
      :width="640"
      unmount-on-close
    >
      <div v-if="testing" style="text-align: center; padding: 24px">
        <a-spin />
      </div>
      <div v-else-if="testResult">
        <div style="margin-bottom: 12px">
          <a-tag v-if="testResult.ok" color="green" size="large">
            <template #icon><icon-check-circle /></template>
            连通正常
          </a-tag>
          <a-tag v-else color="red" size="large">
            <template #icon><icon-close-circle /></template>
            连通失败
          </a-tag>
        </div>
        <div v-if="testResult.message" style="margin-bottom: 8px">
          <strong>信息:</strong> {{ testResult.message }}
        </div>
        <div v-if="testResult.code !== undefined && testResult.code !== null" style="margin-bottom: 8px">
          <strong>错误码:</strong> {{ testResult.code }}
        </div>
        <div v-if="testResult.field_count !== undefined" style="margin-bottom: 8px">
          <strong>字段数:</strong> {{ testResult.field_count }}
        </div>
        <div v-if="testResult.fields?.length">
          <strong>字段列表:</strong>
          <ul style="margin: 4px 0; padding-left: 20px">
            <li v-for="f in testResult.fields" :key="f.id">
              <code>{{ f.name }}</code>
              <span style="color: var(--color-text-3); font-size: 12px">
                (type={{ f.type }}, id={{ f.id }})
              </span>
            </li>
          </ul>
        </div>
      </div>
    </a-modal>

    <!-- 公众号选择器 -->
    <a-modal
      v-model:visible="showMpSelector"
      title="选择公众号"
      :footer="false"
      width="800px"
    >
      <MpMultiSelect
        ref="mpSelectorRef"
        v-model="formData.selected_mps"
      />
      <template #footer>
        <a-button type="primary" @click="showMpSelector = false">确定</a-button>
      </template>
    </a-modal>
  </div>
</template>

<style scoped>
.lark-page { padding: 16px; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
</style>