import request from './request'

export const getRecognitionStatus = () => request.get('/recognition/status')
export const getPresetAvailable = () => request.get('/recognition/preset-available')
export const deployPreset = () => request.post('/recognition/deploy-preset')
export const getTestImages = () => request.get('/recognition/test-images')

export const recognize = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/recognition/recognize', formData)
}
