import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

request.interceptors.response.use(
  (res) => res.data,
  (err) =>
    Promise.reject(
      err.response?.data?.detail || err.response?.data?.error || err.message
    )
)

export default request
