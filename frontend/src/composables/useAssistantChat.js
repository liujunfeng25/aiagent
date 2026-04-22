// AI 助手会话状态：messages、session_id、send、loading、错误提示
import { ref, computed } from 'vue'
import { postChat, streamChat, exportReportDocx } from '../api/chat'

const STORAGE_KEY = 'sx-assistant-session-id'
const MAX_TURNS = 10
const TOOL_LABELS = {
  get_kpi_summary: '核心指标',
  get_top_goods: '商品排行',
  get_top_members: '客户排行',
  get_daily_trend: '日趋势',
  get_intraday_gmv: '今日分时',
  get_region_rank: '区域排行',
  get_category_distribution: '品类分布',
  get_backorder_trend: '退货趋势',
  get_xinfadi_price: '新发地行情',
  get_ops_alerts: '运营告警',
  get_member_orders: '会员下钻',
  get_order_detail: '订单详情',
  get_today_orders: '今日订单',
  get_calendar_heatmap: '日历热力',
  get_schema_overview: '数据范围',
  generate_report: '报告生成',
}

/** 与后端 phase 对齐的占位进度（非精确百分比） */
function phaseToProgress(phase) {
  const map = {
    planning: 22,
    clarify: 28,
    drafting: 42,
    querying: 62,
    answering: 88,
  }
  return map[phase] ?? 18
}

function parseRequestedFormats(text) {
  const t = String(text || '').toLowerCase()
  const formats = []
  if (t.includes('pptx') || t.includes('ppt') || t.includes('powerpoint')) formats.push('pptx')
  if (t.includes('markdown') || t.includes('.md')) formats.push('md')
  if (t.includes('docx') || t.includes('word') || t.includes('文档')) formats.push('docx')
  return formats.length ? [...new Set(formats)] : ['docx']
}

function genSessionId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID()
  return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function loadSessionId() {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v) return v
  } catch (_) {
    /* ignore */
  }
  const id = genSessionId()
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch (_) {
    /* ignore */
  }
  return id
}

/**
 * 每条消息结构：
 *   { id, role: 'user'|'assistant', content: string, data_card?: {...}, report_content?: string, title?: string, error?: boolean }
 */
export function useAssistantChat() {
  const sessionId = ref(loadSessionId())
  const messages = ref([welcomeMessage()])
  const loading = ref(false)
  const lastError = ref('')

  function welcomeMessage() {
    return {
      id: 'welcome',
      role: 'assistant',
      content:
        '您好！我是业务分析助手。您可以问我：\n• 今天哪个区卖得最好？\n• 本月海淀区销售趋势\n• 生成今日日报',
    }
  }

  function reset() {
    messages.value = [welcomeMessage()]
    lastError.value = ''
    sessionId.value = genSessionId()
    try {
      localStorage.setItem(STORAGE_KEY, sessionId.value)
    } catch (_) {
      /* ignore */
    }
  }

  // 将内存消息裁剪为最近 N 轮 user/assistant，交给后端
  const wireMessages = computed(() => {
    const flat = messages.value
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .filter((m) => m.id !== 'welcome')
      .map((m) => ({ role: m.role, content: m.content || '' }))
    // 每轮 = user + assistant 两条
    const keep = MAX_TURNS * 2
    return flat.slice(-keep)
  })

  async function send(text) {
    const trimmed = String(text || '').trim()
    if (!trimmed || loading.value) return
    lastError.value = ''
    const userMsg = { id: genSessionId(), role: 'user', content: trimmed }
    messages.value.push(userMsg)

    loading.value = true
    const placeholder = {
      id: genSessionId(),
      role: 'assistant',
      content: '',
      pending: true,
      phase: '思考中…',
      progress_pct: 8,
      eta_hint: '',
      _answering: false,
      _answerStarted: false,
    }
    messages.value.push(placeholder)

    const tWallStart = typeof performance !== 'undefined' ? performance.now() : Date.now()

    const payload = {
      messages: wireMessages.value,
      session_id: sessionId.value,
    }
    const requestedFormats = parseRequestedFormats(trimmed)

    const getPlaceholder = () =>
      messages.value.find((m) => m.id === placeholder.id)

    const appendProgress = (line) => {
      const it = getPlaceholder()
      if (!it || !line) return
      const base = it.content || ''
      // 避免重复刷同一行
      if (base.endsWith(line) || base.includes(`\n${line}`)) return
      it.content = base ? `${base}\n${line}` : line
    }

    const toToolLabel = (name) => TOOL_LABELS[name] || name || '数据工具'

    const finalizePlaceholder = (res) => {
      if (res?.session_id) sessionId.value = res.session_id
      const idx = messages.value.findIndex((m) => m.id === placeholder.id)
      if (idx >= 0) {
        const wallEnd = typeof performance !== 'undefined' ? performance.now() : Date.now()
        const latencySec = Math.round(((wallEnd - tWallStart) / 1000) * 10) / 10
        const srvMs = res?.server_elapsed_ms
        messages.value.splice(idx, 1, {
          id: placeholder.id,
          role: 'assistant',
          content: res?.reply || placeholder.content || '（空回复）',
          data_card: res?.data_card || null,
          report_content: res?.report_content || null,
          export_formats: Array.isArray(res?.export_formats) ? res.export_formats : requestedFormats,
          title: res?.data_card?.title || null,
          pending: false,
          latency_sec: latencySec,
          server_elapsed_ms: typeof srvMs === 'number' ? srvMs : null,
        })
      }
    }

    try {
      let donePayload = null
      await streamChat(payload, {
        onMeta: (meta) => {
          const idx = messages.value.findIndex((m) => m.id === placeholder.id)
          if (idx >= 0) {
            const row = messages.value[idx]
            row.eta_hint = meta?.hint || row.eta_hint || ''
            row.eta_tier = meta?.tier || row.eta_tier
          }
        },
        onPhase: (e) => {
          const idx = messages.value.findIndex((m) => m.id === placeholder.id)
          if (idx >= 0) {
            messages.value[idx].phase = e?.label || messages.value[idx].phase || '思考中…'
            messages.value[idx]._answering = e?.phase === 'answering'
            const nextP = phaseToProgress(e?.phase)
            const cur = messages.value[idx].progress_pct || 0
            messages.value[idx].progress_pct = Math.max(cur, nextP)
            // 在真正正文出来前，给用户更平滑的进度文案
            if (!messages.value[idx].content) {
              const label = e?.label || '正在处理中…'
              messages.value[idx].content = `进度：${label}`
            }
          }
        },
        onTool: (e) => {
          const idx = messages.value.findIndex((m) => m.id === placeholder.id)
          if (idx >= 0) {
            const cur = messages.value[idx].progress_pct || 0
            messages.value[idx].progress_pct = Math.min(92, cur + 4)
          }
          const name = toToolLabel(e?.name)
          if (e?.status === 'calling') {
            appendProgress(`- 正在查询：${name}`)
          } else if (e?.status === 'done') {
            appendProgress(`- 查询完成：${name}`)
          }
        },
        onDelta: (delta) => {
          if (!delta) return
          const idx = messages.value.findIndex((m) => m.id === placeholder.id)
          if (idx >= 0) {
            const item = messages.value[idx]
            const current = item.content || ''
            // 进入 answering 阶段后的第一段 delta：保留草稿/进度，接上正式结论
            if (item._answering && !item._answerStarted) {
              const prefix = current.trim()
              item.content = prefix
                ? `${prefix}\n\n—— 以下为基于真实数据的正式结论 ——\n${delta}`
                : delta
              item._answerStarted = true
              return
            }
            item.content = current + delta
          }
        },
        onDone: (done) => {
          donePayload = done || {}
        },
        onError: () => {},
      }).catch(() => {
        // 由后续 postChat 兜底
      })

      if (donePayload) {
        finalizePlaceholder(donePayload)
      } else {
        // SSE 异常时回退到普通请求，保证可用性
        const res = await postChat(payload)
        finalizePlaceholder(res)
      }
    } catch (err) {
      const msg = typeof err === 'string' ? err : err?.message || '请求失败'
      lastError.value = msg
      const idx = messages.value.findIndex((m) => m.id === placeholder.id)
      if (idx >= 0) {
        const wallEnd = typeof performance !== 'undefined' ? performance.now() : Date.now()
        const latencySec = Math.round(((wallEnd - tWallStart) / 1000) * 10) / 10
        messages.value.splice(idx, 1, {
          id: placeholder.id,
          role: 'assistant',
          content: `很抱歉，查询失败：${msg}`,
          error: true,
          pending: false,
          latency_sec: latencySec,
          server_elapsed_ms: null,
        })
      }
    } finally {
      loading.value = false
    }
  }

  async function downloadReport({ title, markdown, filename, format }) {
    if (!markdown) return
    const fmt = ['docx', 'pptx', 'md'].includes(format) ? format : 'docx'
    try {
      const blob = await exportReportDocx({ title, markdown, filename, format: fmt })
      const url = window.URL.createObjectURL(new Blob([blob]))
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename || title || 'report'}.${fmt}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      lastError.value = typeof err === 'string' ? err : err?.message || '下载失败'
    }
  }

  return {
    sessionId,
    messages,
    loading,
    lastError,
    send,
    reset,
    downloadReport,
  }
}
