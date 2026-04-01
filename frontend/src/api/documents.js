import request from './request'

const API_BASE = '/api'
const DOC_PREFIX = '/doc'

/** @returns {Promise<{ ocr_engine: string, baidu_key_configured: boolean, using_mock_data: boolean }>} */
export function getDocEngine() {
  return request.get(DOC_PREFIX + '/engine')
}

/**
 * @param {File} file
 * @returns {Promise<{ structured, html_snippet, image_id }>}
 */
export function recognize(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(DOC_PREFIX + '/recognize', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90000,
  })
}

const RECOGNIZE_STREAM_TIMEOUT_MS = 5 * 60 * 1000

/**
 * @param {File} file
 * @param {function(string): void} onProgress
 */
export function recognizeStream(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const url = API_BASE + DOC_PREFIX + '/recognize?stream=1'
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), RECOGNIZE_STREAM_TIMEOUT_MS)
  return new Promise((resolve, reject) => {
    fetch(url, {
      method: 'POST',
      body: form,
      credentials: 'omit',
      signal: controller.signal,
    })
      .then(async (res) => {
        clearTimeout(timeoutId)
        if (!res.ok) {
          const text = await res.text()
          let err = res.statusText
          try {
            const d = JSON.parse(text)
            err = d.detail || (Array.isArray(d.detail) ? d.detail[0]?.msg : null) || text || err
          } catch {
            if (text && text.length < 500) err = text
          }
          reject(new Error(err))
          return
        }
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let result = null
        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              if (result) resolve(result)
              else reject(new Error('未收到识别结果'))
              return
            }
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''
            let event = null
            for (const line of lines) {
              if (line.startsWith('event: ')) event = line.slice(7).trim()
              else if (line.startsWith('data: ') && event) {
                const data = line.slice(6)
                if (event === 'progress' && onProgress) onProgress(data)
                else if (event === 'result') {
                  try {
                    result = JSON.parse(data)
                  } catch (_) {
                    reject(new Error('解析结果失败'))
                  }
                } else if (event === 'error') {
                  reject(new Error(data))
                }
              }
            }
            read()
          }).catch(reject)
        }
        read()
      })
      .catch((err) => {
        clearTimeout(timeoutId)
        if (err.name === 'AbortError') {
          reject(new Error('识别超时（约 5 分钟），请重试。若仍失败可查看后端是否崩溃。'))
        } else if (err.message && err.message.toLowerCase().includes('network')) {
          reject(new Error('连接断开，可能是后端识别时崩溃或超时，请重试并查看后端日志。'))
        } else {
          reject(err)
        }
      })
  })
}

/**
 * @param {object} docA
 * @param {object} docB
 * @param {object} options - { match_key, compare_fields }
 */
export function compare(docA, docB, options = {}) {
  return request.post(DOC_PREFIX + '/compare', {
    doc_a: docA,
    doc_b: docB,
    rules: {
      match_key: options.match_key || '品名',
      compare_fields: options.compare_fields || ['数量', '单位'],
    },
  })
}

/** @returns {Promise<{ kinds: Array<{value,label,table}> }>} */
export function getCompareDocKinds() {
  return request.get(DOC_PREFIX + '/compare-order/doc-kinds')
}

/**
 * @param {object} structured - recognize 返回的 structured
 * @param {{ orderSn?: string, docKind?: string, sendDate?: string, goodsHints?: string[] }} options
 */
export function compareOrderWithDb(structured, options = {}) {
  return request.post(DOC_PREFIX + '/compare-order', {
    structured,
    order_sn: options.orderSn || null,
    doc_kind: options.docKind || 'delivery',
    send_date: options.sendDate || null,
    goods_hints: options.goodsHints?.length ? options.goodsHints : null,
  })
}
