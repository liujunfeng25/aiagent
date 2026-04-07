const LS_KEY = 'sxw_logistics_supp_code'
/** 公司默认租户编码（与食迅后台 supp_code 一致，解析为库名 supp_10133） */
const DEFAULT_COMPANY_SUPP_CODE = '10133'

/** 与食迅后台 $_SESSION['supp_code'] 一致，可为纯数字 ID、supp_ 前缀或 edu_std_supp */
export function getSxwLogisticsSuppCode() {
  if (typeof localStorage === 'undefined') return DEFAULT_COMPANY_SUPP_CODE
  return (
    localStorage.getItem(LS_KEY) ||
    (import.meta.env.VITE_SXW_SUPP_CODE || '').trim() ||
    DEFAULT_COMPANY_SUPP_CODE
  ).trim()
}

export function setSxwLogisticsSuppCode(value) {
  if (typeof localStorage === 'undefined') return
  const v = (value || '').trim()
  if (v) localStorage.setItem(LS_KEY, v)
  else localStorage.removeItem(LS_KEY)
}

/** 合并到 axios params，用于 GET / 部分 POST 的 query */
export function sxwLogisticsAxiosParams(extra = {}) {
  const s = getSxwLogisticsSuppCode()
  if (!s) return { ...extra }
  return { ...extra, supp_code: s }
}
