/** 假登录态（sessionStorage，关闭标签即失效） */
export const AUTH_STORAGE_KEY = 'aiagent_auth'

export function isLoggedIn() {
  return sessionStorage.getItem(AUTH_STORAGE_KEY) === '1'
}

export function setLoggedIn() {
  sessionStorage.setItem(AUTH_STORAGE_KEY, '1')
}

export function clearLoggedIn() {
  sessionStorage.removeItem(AUTH_STORAGE_KEY)
}
