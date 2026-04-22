import request from './request'

export function postChat({ messages, session_id }) {
  return request.post('/chat', { messages, session_id })
}

/**
 * 下载报告：默认 docx，支持 pptx / md。
 * @param {object} p
 * @param {string} p.title
 * @param {string} p.markdown
 * @param {string} [p.filename]
 * @param {'docx'|'pptx'|'md'} [p.format]
 */
export function exportReportDocx({ title, markdown, filename, format }) {
  return request.post(
    '/chat/report/export',
    { title, markdown, filename, format: format || 'docx' },
    { responseType: 'blob' },
  )
}

export function getCatalog() {
  return request.get('/chat/catalog')
}

export function refreshCatalog() {
  return request.post('/chat/catalog/refresh', {})
}

/**
 * SSE 流式对话。EventSource 不支持 POST，所以这里用 fetch + ReadableStream。
 *
 * 事件列表：
 * - meta   : { tier, eta_sec_min, eta_sec_max, hint }
 * - phase  : { phase, label }
 * - intent : { intent, already_clarifying }
 * - tool   : { name, status }
 * - delta  : { text }
 * - done   : { reply, data_card, report_content, session_id, debug, server_elapsed_ms }
 * - error  : { message }
 *
 * @param {object} payload                    请求体
 * @param {object} handlers                   回调集合
 * @param {(e:object)=>void} [handlers.onMeta]
 * @param {(e:object)=>void} [handlers.onPhase]
 * @param {(e:object)=>void} [handlers.onIntent]
 * @param {(e:object)=>void} [handlers.onTool]
 * @param {(text:string)=>void} [handlers.onDelta]
 * @param {(done:object)=>void} [handlers.onDone]
 * @param {(err:Error)=>void} [handlers.onError]
 * @param {AbortSignal} [handlers.signal]
 */
export async function streamChat(payload, handlers = {}) {
  const { onMeta, onPhase, onIntent, onTool, onDelta, onDone, onError, signal } = handlers
  const baseURL = (request.defaults && request.defaults.baseURL) || '/api'
  const url = baseURL.replace(/\/$/, '') + '/chat/stream'

  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      signal,
    })
  } catch (e) {
    onError && onError(e)
    throw e
  }

  if (!resp.ok || !resp.body) {
    const err = new Error(`HTTP ${resp.status}`)
    onError && onError(err)
    throw err
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  function dispatch(event, data) {
    let parsed
    try {
      parsed = JSON.parse(data)
    } catch {
      return
    }
    switch (event) {
      case 'meta':
        onMeta && onMeta(parsed)
        break
      case 'phase':
        onPhase && onPhase(parsed)
        break
      case 'intent':
        onIntent && onIntent(parsed)
        break
      case 'tool':
        onTool && onTool(parsed)
        break
      case 'delta':
        onDelta && onDelta(parsed.text || '')
        break
      case 'done':
        onDone && onDone(parsed)
        break
      case 'error':
        onError && onError(new Error(parsed.message || 'stream error'))
        break
      default:
        break
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 按双换行分帧
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const lines = raw.split('\n')
      let event = 'message'
      const dataLines = []
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^\s/, ''))
      }
      if (dataLines.length) dispatch(event, dataLines.join('\n'))
    }
  }
}
