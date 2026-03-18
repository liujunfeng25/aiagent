import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err.response?.data?.detail || err.message)
)

export default request
