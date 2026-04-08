<template>
  <div class="documents-page">
    <div class="page-header">
      <h2 class="page-title">票据识别</h2>
      <p class="page-desc">表格 / 票据 OCR（百度或演示模式），与「识别中心」的图像分类不同。支持发货单与收货单对比。</p>
    </div>

    <el-alert
      v-if="engineInfo?.using_mock_data"
      type="warning"
      show-icon
      :closable="false"
      class="engine-alert"
      title="当前为演示模式（本地模拟数据）"
      description="未配置百度表格识别密钥，结果固定为示例表格（如白菜、萝卜）。请在 backend/.env 设置 DOCUMENTS_BAIDU_TABLE_API_KEY；若本机另有 puaojuchuli 项目，可将其放在与 ai-agent 同一父目录下（例如均为磁盘根下子文件夹），系统会自动尝试读取其 backend/config.py 中的密钥。修改后需重启后端。"
    />
    <el-alert
      v-else-if="engineInfo && !engineInfo.baidu_key_configured && engineInfo.ocr_engine === 'baidu'"
      type="error"
      show-icon
      :closable="false"
      class="engine-alert"
      title="已选择百度引擎但未检测到有效密钥"
      description="请检查环境变量 DOCUMENTS_BAIDU_TABLE_API_KEY。"
    />

    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="识别" name="recognize">
        <el-card class="upload-card" shadow="never">
          <el-row :gutter="24">
            <el-col :xs="24" :md="10">
              <div class="upload-area">
                <el-upload
                  class="upload-demo"
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="onFileChange"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
                </el-upload>
                <div class="upload-hint">单张图片不超过 {{ MAX_FILE_SIZE_MB }}MB</div>
                <el-button
                  type="primary"
                  size="large"
                  :loading="recognizing"
                  :disabled="!currentFile"
                  @click="doRecognize"
                  class="btn-recognize"
                >
                  {{ recognizing ? '识别中…' : '开始识别' }}
                </el-button>
                <div v-if="recognizing || progressText" class="progress-text">
                  {{ progressText || '正在连接…' }}
                </div>
              </div>
              <div v-if="previewUrl" class="preview-img-wrap">
                <img :src="previewUrl" alt="预览" class="preview-img" />
              </div>
            </el-col>
            <el-col :xs="24" :md="14">
              <div v-if="!recognizeResult" class="result-placeholder">
                <p>上传图片并点击「开始识别」后，识别表格在下方展示；右侧可与业务库对账。</p>
              </div>
              <div v-else class="db-compare-panel">
                <h4 class="db-compare-title">与系统对账</h4>
                <p class="db-compare-desc">
                  请选择单据类型，系统将到对应业务表拉取数据与识别结果比对。送货/收货单若无印刷订单号可留空，凭图中司机手机号匹配；同一司机多条时可选择送货日期收窄；若仍多条，可填写「品名关键词」或依赖识别表格品名与系统订单明细自动择优。采购/入库单请尽量填写单号。
                </p>
                <el-form label-position="top" class="db-compare-form">
                  <el-form-item label="单据类型">
                    <el-select v-model="docKind" style="width: 100%" @change="runDbCompare">
                      <el-option
                        v-for="opt in docKindOptions"
                        :key="opt.value"
                        :label="opt.label"
                        :value="opt.value"
                      >
                        <span>{{ opt.label }}</span>
                        <span v-if="opt.table" class="opt-table-hint">{{ opt.table }}</span>
                      </el-option>
                    </el-select>
                  </el-form-item>
                  <el-form-item label="订单号 / 采购单号（可选）">
                    <el-input
                      v-model="compareOrderSn"
                      clearable
                      placeholder="有印刷单号时填写；无单号请留空，勿把送货日期填在这里"
                      @keyup.enter="runDbCompare"
                    />
                  </el-form-item>
                  <el-form-item v-if="docKind !== 'procurement'" label="送货日期（可选）">
                    <el-date-picker
                      v-model="compareSendDate"
                      type="date"
                      value-format="YYYY-MM-DD"
                      placeholder="与单号同为空时会尝试从识别结果取；手机号多条时选此可收窄"
                      style="width: 100%"
                      clearable
                    />
                  </el-form-item>
                  <el-form-item v-if="docKind !== 'procurement'" label="品名关键词（可选）">
                    <el-input
                      v-model="compareGoodsHints"
                      type="textarea"
                      :rows="2"
                      clearable
                      placeholder="多条订单无法区分时，填写单据上的品名，多个用逗号、顿号或换行分隔；将与系统订单明细比对以收窄"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :loading="dbCompareLoading" @click="runDbCompare">
                      重新对账
                    </el-button>
                  </el-form-item>
                </el-form>
                <el-skeleton v-if="dbCompareLoading" :rows="4" animated />
                <template v-else-if="dbCompareResult">
                  <el-alert
                    v-if="dbCompareResult.ok === false"
                    type="warning"
                    show-icon
                    :closable="false"
                    :title="dbCompareResult.reason || '无法对账'"
                    class="db-compare-alert"
                  />
                  <el-alert
                    v-else-if="dbCompareResult.matched && dbCompareResult.consistent"
                    type="success"
                    show-icon
                    :closable="false"
                    title="数据一致"
                    description="当前识别结果与业务库中对应单据在已比对字段上未发现差异。"
                    class="db-compare-alert"
                  />
                  <template v-else-if="dbCompareResult.matched && !dbCompareResult.consistent">
                    <el-alert
                      type="info"
                      show-icon
                      :closable="false"
                      :title="`已匹配单号 ${dbCompareResult.order_sn || dbCompareResult.order_id || ''}`"
                      class="db-compare-alert"
                    />
                    <div v-if="(dbCompareResult.header_diffs || []).length" class="db-diff-block">
                      <div class="db-diff-label">表头/汇总差异</div>
                      <el-table :data="dbCompareResult.header_diffs" border size="small" max-height="200">
                        <el-table-column prop="field" label="字段" width="120" />
                        <el-table-column prop="ocr" label="识别值" show-overflow-tooltip />
                        <el-table-column prop="db" label="系统值" show-overflow-tooltip />
                      </el-table>
                    </div>
                    <div v-if="(dbCompareResult.line_diffs || []).length" class="db-diff-block">
                      <div class="db-diff-label">明细差异</div>
                      <el-table :data="dbCompareResult.line_diffs" border size="small" max-height="280">
                        <el-table-column prop="goods" label="品名" width="130" show-overflow-tooltip />
                        <el-table-column prop="field" label="项" width="140" show-overflow-tooltip />
                        <el-table-column prop="ocr" label="识别" min-width="90" show-overflow-tooltip />
                        <el-table-column prop="db" label="系统" min-width="90" show-overflow-tooltip />
                      </el-table>
                    </div>
                    <div
                      v-if="(dbCompareResult.only_in_ocr || []).length || (dbCompareResult.only_in_db || []).length"
                      class="db-diff-block"
                    >
                      <div class="db-diff-label">仅一侧存在的品名</div>
                      <p v-if="(dbCompareResult.only_in_ocr || []).length" class="db-only-line">
                        仅识别有：
                        {{
                          (dbCompareResult.only_in_ocr || []).map((x) => x.goods).filter(Boolean).join('、') || '—'
                        }}
                      </p>
                      <p v-if="(dbCompareResult.only_in_db || []).length" class="db-only-line">
                        仅系统有：
                        {{
                          (dbCompareResult.only_in_db || []).map((x) => x.goods).filter(Boolean).join('、') || '—'
                        }}
                      </p>
                    </div>
                  </template>
                  <el-alert
                    v-else-if="dbCompareResult.ok && dbCompareResult.matched === false"
                    type="warning"
                    show-icon
                    :closable="false"
                    :title="dbCompareResult.message || '未匹配到业务单据'"
                    class="db-compare-alert"
                  />
                </template>
              </div>
            </el-col>
          </el-row>

          <template v-if="recognizeResult">
            <el-divider content-position="left">识别结果</el-divider>
            <div class="result-full">
              <div v-if="(recognizeResult.structured?.key_values || []).length" class="kv-section">
                <div class="kv-list">
                  <span
                    v-for="(kv, idx) in (recognizeResult.structured.key_values || [])"
                    :key="idx"
                    class="kv-item"
                  >
                    <strong>{{ kv.key }}:</strong> {{ kv.value }}
                  </span>
                </div>
              </div>
              <el-alert
                v-if="hasRemarkHighlight"
                type="warning"
                show-icon
                :closable="false"
                class="handwriting-alert"
                title="备注列有内容"
                description="以下标红为备注列中填写了内容的单元格，可能存在手写/改动，请重点复核。"
              />
              <el-alert
                v-else-if="(recognizeResult.structured?.tables || []).length > 0"
                type="info"
                show-icon
                :closable="false"
                class="handwriting-alert"
                title="备注列暂无填写内容"
                description="当前表格中备注列无识别到的文字，故未做标红。若原图备注列有内容却未标红，请检查表头是否识别为「备注」或重新上传更清晰的图片。"
              />
              <div
                v-for="(tbl, i) in (recognizeResult.structured?.tables || [])"
                :key="i"
                class="table-scroll-wrap"
              >
                <el-table
                  :data="tbl.rows"
                  border
                  stripe
                  size="default"
                  class="result-table"
                >
                  <el-table-column
                    v-for="(h, j) in tbl.headers"
                    :key="j"
                    :prop="String(j)"
                    :label="h"
                    :min-width="h && h.length > 8 ? 140 : 100"
                  >
                    <template #default="{ row, $index }">
                      <span :class="{ 'cell-handwriting': isRemarkCellWithContent(i, $index, j) }">
                        {{ row[j] }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </template>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="对比" name="compare">
        <el-card shadow="hover">
          <p class="tip">分别上传发货单与收货单图片并识别，得到两份结构化数据后执行对比。</p>
          <el-row :gutter="16" style="margin-bottom: 16px">
            <el-col :span="12">
              <div class="compare-card">
                <h4>单据 A（发货单）</h4>
                <el-upload
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="(f) => onCompareFileChange(f, 'a')"
                >
                  <span v-if="!docA">上传图片识别（≤{{ MAX_FILE_SIZE_MB }}MB）</span>
                  <span v-else>已解析，可重新上传</span>
                </el-upload>
                <el-button
                  v-if="fileA"
                  type="primary"
                  size="small"
                  :loading="loadingA"
                  @click="recognizeForCompare('a')"
                  style="margin-top: 8px"
                >
                  识别
                </el-button>
                <div v-if="progressA" class="mini-summary progress-inline">{{ progressA }}</div>
                <div v-else-if="docA" class="mini-summary">表格行数: {{ tableRowCount(docA) }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="compare-card">
                <h4>单据 B（收货单）</h4>
                <el-upload
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="(f) => onCompareFileChange(f, 'b')"
                >
                  <span v-if="!docB">上传图片识别（≤{{ MAX_FILE_SIZE_MB }}MB）</span>
                  <span v-else>已解析，可重新上传</span>
                </el-upload>
                <el-button
                  v-if="fileB"
                  type="primary"
                  size="small"
                  :loading="loadingB"
                  @click="recognizeForCompare('b')"
                  style="margin-top: 8px"
                >
                  识别
                </el-button>
                <div v-if="progressB" class="mini-summary progress-inline">{{ progressB }}</div>
                <div v-else-if="docB" class="mini-summary">表格行数: {{ tableRowCount(docB) }}</div>
              </div>
            </el-col>
          </el-row>
          <el-button
            type="primary"
            :disabled="!docA || !docB || comparing"
            :loading="comparing"
            @click="doCompare"
          >
            {{ comparing ? '对比中…' : '执行对比' }}
          </el-button>
          <div v-if="compareResult" class="compare-result">
            <h4>对比摘要</h4>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="涉及品名数">{{ compareResult.summary?.total_keys ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="差异条数">{{ compareResult.summary?.diff_count ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="仅 A 有">仅发货单有: {{ compareResult.summary?.only_in_a ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="仅 B 有">仅收货单有: {{ compareResult.summary?.only_in_b ?? '-' }}</el-descriptions-item>
            </el-descriptions>
            <h4 style="margin-top: 16px">差异明细（同一品名下单据 A/B 字段值不一致）</h4>
            <el-table :data="compareResult.diffs" border size="small">
              <el-table-column prop="key" label="品名/键" width="120" />
              <el-table-column prop="field" label="字段" width="80" />
              <el-table-column prop="value_a" label="单据 A 值" />
              <el-table-column prop="value_b" label="单据 B 值" />
              <el-table-column prop="match" label="一致" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.match ? 'success' : 'danger'" size="small">
                    {{ row.match ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <template v-if="onlyInA.length || onlyInB.length">
              <h4 style="margin-top: 16px">仅发货单有（收货单无）</h4>
              <el-table :data="onlyInARows" border size="small" style="margin-bottom: 16px">
                <el-table-column v-for="h in onlyInAHeaders" :key="h" :prop="h" :label="h" min-width="80" show-overflow-tooltip />
              </el-table>
              <h4 style="margin-top: 16px">仅收货单有（发货单无）</h4>
              <el-table :data="onlyInBRows" border size="small">
                <el-table-column v-for="h in onlyInBHeaders" :key="h" :prop="h" :label="h" min-width="80" show-overflow-tooltip />
              </el-table>
            </template>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { recognizeStream, compare, getDocEngine, compareOrderWithDb, getCompareDocKinds } from '../api/documents'

const engineInfo = ref(null)
const docKindOptions = ref([
  { value: 'delivery', label: '送货单（销售出货）', table: 'orders' },
  { value: 'receipt', label: '收货单（客户签收回单）', table: 'orders' },
  { value: 'procurement', label: '采购/入库单', table: 'procurement_orders' },
])
const docKind = ref('delivery')
const compareOrderSn = ref('')
const compareSendDate = ref(null)
const compareGoodsHints = ref('')
const dbCompareLoading = ref(false)
const dbCompareResult = ref(null)

onMounted(async () => {
  try {
    engineInfo.value = await getDocEngine()
  } catch {
    engineInfo.value = null
  }
  try {
    const res = await getCompareDocKinds()
    if (res?.kinds?.length) docKindOptions.value = res.kinds
  } catch {
    /* 使用默认 docKindOptions */
  }
})

const MAX_FILE_SIZE_MB = 20
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

const activeTab = ref('recognize')
const currentFile = ref(null)
const previewUrl = ref('')
const recognizing = ref(false)
const progressText = ref('')
const recognizeResult = ref(null)

function parseCompareErr(e) {
  if (typeof e === 'string') return e
  if (e?.detail) return Array.isArray(e.detail) ? e.detail.map((x) => x.msg || x).join('; ') : String(e.detail)
  return String(e?.message || e || '对账请求失败')
}

/** @returns {string[] | undefined} */
function splitGoodsHints(raw) {
  if (raw == null || !String(raw).trim()) return undefined
  const parts = String(raw)
    .trim()
    .split(/[,，、;；\n\r]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return parts.length ? parts.slice(0, 50) : undefined
}

async function runDbCompare() {
  if (!recognizeResult.value?.structured) return
  dbCompareLoading.value = true
  dbCompareResult.value = null
  try {
    dbCompareResult.value = await compareOrderWithDb(recognizeResult.value.structured, {
      orderSn: compareOrderSn.value?.trim() || undefined,
      docKind: docKind.value,
      sendDate:
        docKind.value !== 'procurement' && compareSendDate.value ? compareSendDate.value : undefined,
      goodsHints: docKind.value !== 'procurement' ? splitGoodsHints(compareGoodsHints.value) : undefined,
    })
  } catch (e) {
    dbCompareResult.value = { ok: false, reason: parseCompareErr(e) }
  } finally {
    dbCompareLoading.value = false
  }
}

function isRemarkColumnHeader(label, colIndex, headers) {
  const s = label != null ? String(label).trim() : ''
  if (s === '备注' || s.includes('备注') || s === '注') return true
  if (headers && colIndex === headers.length - 1 && !/总价|金额|单价|数量|折扣|原价|折后/.test(s)) return true
  return false
}

const hasRemarkHighlight = computed(() => {
  const tables = recognizeResult.value?.structured?.tables || []
  return tables.some(t => {
    const headers = t?.headers || []
    const rows = t?.rows || []
    const remarkColIdx = headers.findIndex((h, idx) => isRemarkColumnHeader(h, idx, headers))
    if (remarkColIdx === -1) return false
    return rows.some(row => {
      const val = row[remarkColIdx]
      return val != null && String(val).trim() !== ''
    })
  })
})

function isRemarkCellWithContent(tableIndex, rowIndex, colIndex) {
  const tbl = recognizeResult.value?.structured?.tables?.[tableIndex]
  const headers = tbl?.headers || []
  const label = headers[colIndex]
  if (!isRemarkColumnHeader(label, colIndex, headers)) return false
  const row = tbl?.rows?.[rowIndex]
  if (!row) return false
  const val = row[colIndex]
  return val != null && String(val).trim() !== ''
}

function onFileChange(file) {
  const f = file?.raw
  if (f && f.size > MAX_FILE_SIZE_BYTES) {
    ElMessage.warning(`图片大小不能超过 ${MAX_FILE_SIZE_MB}MB，当前 ${(f.size / 1024 / 1024).toFixed(1)}MB`)
    currentFile.value = null
    previewUrl.value = ''
    recognizeResult.value = null
    dbCompareResult.value = null
    return
  }
  currentFile.value = f || null
  previewUrl.value = f ? URL.createObjectURL(f) : ''
  recognizeResult.value = null
  dbCompareResult.value = null
}

async function doRecognize() {
  if (!currentFile.value) return
  recognizing.value = true
  progressText.value = ''
  recognizeResult.value = null
  dbCompareResult.value = null
  try {
    const data = await recognizeStream(currentFile.value, (msg) => {
      progressText.value = msg
    })
    recognizeResult.value = data
    progressText.value = ''
    ElMessage.success('识别完成')
    await runDbCompare()
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e?.detail || e?.message || (Array.isArray(e?.detail) ? e.detail[0]?.msg : null) || '识别失败')
    ElMessage.error(msg)
    progressText.value = ''
  } finally {
    recognizing.value = false
  }
}

const fileA = ref(null)
const fileB = ref(null)
const docA = ref(null)
const docB = ref(null)
const loadingA = ref(false)
const loadingB = ref(false)
const progressA = ref('')
const progressB = ref('')
const comparing = ref(false)
const compareResult = ref(null)

const onlyInA = computed(() => {
  const matches = compareResult.value?.matches || []
  return matches
    .filter(m => (m.in_a ?? m.inA) && !(m.in_b ?? m.inB))
    .map(m => ({ key: m.key, row: m.row_a ?? m.rowA ?? [], headers: m.headers_a ?? m.headersA ?? [] }))
})
const onlyInB = computed(() => {
  const matches = compareResult.value?.matches || []
  return matches
    .filter(m => (m.in_b ?? m.inB) && !(m.in_a ?? m.inA))
    .map(m => ({ key: m.key, row: m.row_b ?? m.rowB ?? [], headers: m.headers_b ?? m.headersB ?? [] }))
})
const onlyInAHeaders = computed(() => {
  const fromMatch = onlyInA.value[0]?.headers
  if (fromMatch?.length) return fromMatch
  const fromDoc = docA.value?.tables?.[0]?.headers
  if (fromDoc?.length) return fromDoc
  return ['品名/键']
})
const onlyInBHeaders = computed(() => {
  const fromMatch = onlyInB.value[0]?.headers
  if (fromMatch?.length) return fromMatch
  const fromDoc = docB.value?.tables?.[0]?.headers
  if (fromDoc?.length) return fromDoc
  return ['品名/键']
})
const onlyInARows = computed(() => {
  const headers = onlyInAHeaders.value
  if (!headers.length) return onlyInA.value.map(m => ({ '品名/键': m.key }))
  return onlyInA.value.map(m => {
    const row = m.row || []
    const obj = {}
    headers.forEach((h, i) => {
      obj[h] = (headers.length === 1 && h === '品名/键') ? m.key : (row[i] ?? '')
    })
    return obj
  })
})
const onlyInBRows = computed(() => {
  const headers = onlyInBHeaders.value
  if (!headers.length) return onlyInB.value.map(m => ({ '品名/键': m.key }))
  return onlyInB.value.map(m => {
    const row = m.row || []
    const obj = {}
    headers.forEach((h, i) => {
      obj[h] = (headers.length === 1 && h === '品名/键') ? m.key : (row[i] ?? '')
    })
    return obj
  })
})

function onCompareFileChange(file, which) {
  const f = file?.raw
  if (f && f.size > MAX_FILE_SIZE_BYTES) {
    ElMessage.warning(`图片大小不能超过 ${MAX_FILE_SIZE_MB}MB，当前 ${(f.size / 1024 / 1024).toFixed(1)}MB`)
    if (which === 'a') {
      fileA.value = null
      docA.value = null
    } else {
      fileB.value = null
      docB.value = null
    }
    compareResult.value = null
    return
  }
  if (which === 'a') {
    fileA.value = f || null
    if (!f) docA.value = null
  } else {
    fileB.value = f || null
    if (!f) docB.value = null
  }
  compareResult.value = null
}

async function recognizeForCompare(which) {
  const file = which === 'a' ? fileA.value : fileB.value
  if (!file) return
  if (which === 'a') {
    loadingA.value = true
    progressA.value = ''
  } else {
    loadingB.value = true
    progressB.value = ''
  }
  try {
    const data = await recognizeStream(file, (msg) => {
      if (which === 'a') progressA.value = msg
      else progressB.value = msg
    })
    if (which === 'a') {
      docA.value = data.structured
      progressA.value = ''
    } else {
      docB.value = data.structured
      progressB.value = ''
    }
    ElMessage.success('识别完成')
  } catch (e) {
    const msg = typeof e === 'string' ? e : (e?.message || '识别失败')
    ElMessage.error(msg)
    if (which === 'a') progressA.value = ''
    else progressB.value = ''
  } finally {
    if (which === 'a') loadingA.value = false
    else loadingB.value = false
  }
}

function tableRowCount(doc) {
  const tables = doc?.tables
  if (!tables?.length) return 0
  return (tables[0].rows || []).length
}

async function doCompare() {
  if (!docA.value || !docB.value) return
  comparing.value = true
  compareResult.value = null
  try {
    const data = await compare(docA.value, docB.value, {
      match_key: '品名',
      compare_fields: ['数量', '单位'],
    })
    compareResult.value = data
    ElMessage.success('对比完成')
  } catch (e) {
    ElMessage.error(e?.message || '对比失败')
  } finally {
    comparing.value = false
  }
}
</script>

<style scoped>
.engine-alert {
  margin-bottom: 16px;
}
.page-header {
  margin-bottom: 24px;
}
.page-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--sx-text-title);
  letter-spacing: 0.03em;
  text-shadow: var(--sx-text-shadow-readable);
}
.page-desc {
  margin: 0;
  font-size: 14px;
  color: var(--sx-text-readable-muted);
  line-height: 1.6;
  max-width: 72ch;
  text-shadow: var(--sx-text-shadow-strong);
}
.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.upload-card {
  border-radius: var(--sx-radius-panel);
}
.upload-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--sx-text-readable-dim);
}
.btn-recognize {
  margin-top: 12px;
}
.preview-img-wrap {
  margin-top: 16px;
}
.preview-img {
  max-width: 100%;
  max-height: 320px;
  border-radius: 8px;
  border: 1px solid var(--sx-glass-border);
}
.result-placeholder {
  color: var(--sx-text-readable-muted);
  padding: 48px 24px;
  text-align: center;
  background: rgba(12, 18, 40, 0.72);
  border: 1px dashed var(--sx-edge-cyan-mid);
  border-radius: var(--sx-radius-panel);
  font-size: 14px;
  line-height: 1.55;
  text-shadow: var(--sx-text-shadow-readable);
}
.db-compare-panel {
  padding: 16px;
  background: rgba(10, 17, 38, 0.82);
  border: 1px solid var(--sx-glass-border);
  border-radius: var(--sx-radius-panel);
  min-height: 120px;
  backdrop-filter: blur(10px);
}
.db-compare-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--sx-text-bright);
}
.db-compare-desc {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: var(--sx-text-readable-muted);
  line-height: 1.55;
}
.db-compare-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.opt-table-hint {
  float: right;
  color: var(--sx-text-dim);
  font-size: 12px;
  margin-left: 8px;
}
.db-compare-alert {
  margin-top: 12px;
}
.db-diff-block {
  margin-top: 12px;
}
.db-diff-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--sx-text-body);
  margin-bottom: 8px;
}
.db-only-line {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: var(--sx-text-readable-muted);
  line-height: 1.5;
}
.result-full {
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid var(--sx-edge-cyan-mid);
}
.kv-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  font-size: 14px;
  color: var(--sx-text-body);
  margin-bottom: 16px;
}
.kv-item strong {
  color: var(--sx-text-bright);
  margin-right: 4px;
}
.table-scroll-wrap {
  overflow-x: auto;
  margin-bottom: 24px;
}
.handwriting-alert {
  margin: 8px 0 16px 0;
}
.result-table {
  min-width: max-content;
}
.cell-handwriting {
  color: #fecaca;
  font-weight: 700;
  background: rgba(127, 29, 29, 0.45);
  padding: 2px 6px;
  border-radius: 6px;
}
.compare-result h4 {
  font-size: 14px;
  color: var(--sx-text-readable-muted);
  margin-bottom: 8px;
  font-weight: 600;
}
.tip {
  color: var(--sx-text-readable-muted);
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.55;
}
.compare-card {
  padding: 12px;
  border: 1px solid var(--sx-glass-border);
  border-radius: var(--sx-radius-panel);
  background: rgba(10, 17, 38, 0.75);
  backdrop-filter: blur(8px);
}
.compare-card h4 {
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--sx-text-title);
}
.mini-summary {
  margin-top: 8px;
  font-size: 12px;
  color: var(--sx-text-readable-dim);
}
.progress-text,
.progress-inline {
  margin-top: 8px;
  font-size: 13px;
  color: var(--sx-cyan-light);
}
.compare-result {
  margin-top: 20px;
}
</style>
