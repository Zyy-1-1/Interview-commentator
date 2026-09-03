/**
 * 浏览器端语音播报(端侧 TTS,零服务器成本)。
 * speaking 状态同时驱动数字人口型动画。
 */
import { onBeforeUnmount, reactive } from 'vue'

const VOICE_PREF = [
  'Microsoft Xiaoxiao', // Win11 中文女声
  'Microsoft Huihui',
  'Microsoft Yunxi',
  'Ting-Ting',
  'Google 普通话',
]

export function useSpeech() {
  const supported =
    typeof window !== 'undefined' && 'speechSynthesis' in window

  const state = reactive({
    enabled: supported,
    speaking: false,
  })

  function pickVoice(pitch) {
    const voices = window.speechSynthesis.getVoices()
    const zh = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith('zh'))
    let voice = null
    for (const pref of VOICE_PREF) {
      voice = zh.find((v) => v.name.includes(pref))
      if (voice) break
    }
    return voice || zh[0] || null
  }

  function speak(text, { pitch = 1, rate = 1.02 } = {}) {
    if (!supported || !state.enabled || !text) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    const v = pickVoice(pitch)
    if (v) u.voice = v
    u.pitch = pitch
    u.rate = rate
    u.onstart = () => (state.speaking = true)
    u.onend = () => (state.speaking = false)
    u.onerror = () => (state.speaking = false)
    window.speechSynthesis.speak(u)
  }

  function stop() {
    if (supported) window.speechSynthesis.cancel()
    state.speaking = false
  }

  function toggle() {
    state.enabled = !state.enabled
    if (!state.enabled) stop()
  }

  const warmVoices = () => window.speechSynthesis.getVoices()

  // Chrome 的 voice 列表异步加载,只注册本组件监听，不覆盖页面上的其他监听器。
  if (supported) {
    window.speechSynthesis.addEventListener('voiceschanged', warmVoices)
    warmVoices()
  }

  onBeforeUnmount(() => {
    if (supported) {
      window.speechSynthesis.removeEventListener('voiceschanged', warmVoices)
    }
    stop()
  })

  return { supported, speaking: () => state.speaking, state, speak, stop, toggle }
}
