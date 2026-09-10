<template>
  <div class="page">
    <header class="topbar">
      <div class="interviewer">
        <DigitalHuman :style="chosenStyle" :speaking="speech.state.speaking" small />
        <div class="who">
          <b>{{ personaName }}</b>
          <span>AI 模拟面试官</span>
        </div>
      </div>
      <div class="top-right">
        <div class="progress-chips" v-if="hasProgress">
          <span class="chip phase" :class="phaseKey || 'created'">{{ phaseText }}</span>
          <span class="chip dimension" v-if="state.progress.current_dimension">
            {{ state.progress.current_dimension }}
          </span>
          <span class="chip round">{{ asked }}/{{ total }} 轮</span>
        </div>
        <button
          class="voice-btn"
          v-if="speech.supported"
          :title="speech.state.enabled ? '关闭语音播报' : '开启语音播报'"
          @click="speech.toggle()"
        >
          {{ speech.state.enabled ? '🔊' : '🔇' }}
        </button>
      </div>
      <div class="progressbar" v-if="hasProgress">
        <div class="progressbar-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
    </header>

    <!-- 未开始:选择面试官风格 -->
    <main class="chat picker-chat" v-if="showPicker">
      <div class="picker panel">
        <h1>选择你的 AI 面试官</h1>
        <p class="sub">选定后即可开始模拟面试；如设备支持，可在右上角开启语音播报。</p>
        <div class="styles">
          <label v-for="s in STYLES" :key="s.key" class="style" :class="{ on: chosenStyle === s.key }">
            <input type="radio" :value="s.key" v-model="chosenStyle" />
            <DigitalHuman :style="s.key" />
            <b>{{ s.name }}</b>
            <span>{{ s.desc }}</span>
          </label>
        </div>
        <button class="primary" :disabled="starting" @click="pickAndStart">
          {{ starting ? '面试官入场中…' : `开始面试(与${styleName})` }}
        </button>
        <div v-if="state.error" class="picker-error" role="alert">
          <p class="err">{{ state.error }}</p>
          <router-link class="return-link" to="/">返回岗位大厅</router-link>
        </div>
      </div>
    </main>

    <main class="chat" ref="chatBox" v-else>
      <div v-if="state.loading" class="center">
        <span class="dots"><i></i><i></i><i></i></span>
        正在连接面试官…
      </div>
      <div v-else-if="state.error && !state.messages.length" class="center error">
        <b>无法继续这场面试</b>
        <p>{{ state.error }}</p>
        <div class="error-actions">
          <button v-if="accessToken" class="retry" @click="retryBoot">重新连接</button>
          <router-link class="return-link" to="/">返回岗位大厅</router-link>
        </div>
      </div>
      <template v-else>
        <div v-for="(m, i) in state.messages" :key="i" class="msg" :class="m.role">
          <DigitalHuman
            v-if="m.role === 'agent'"
            class="message-human"
            :style="chosenStyle"
            small
          />
          <div v-else class="avatar" aria-label="候选人">我</div>
          <div class="bubble-wrap">
            <span v-if="m.dimension" class="message-dimension">考察维度 · {{ m.dimension }}</span>
            <div class="bubble">{{ m.text }}</div>
          </div>
        </div>

        <!-- 发送失败:可重试的错误卡片 -->
        <div v-if="state.failed" class="msg candidate">
          <div class="fail-card">
            <div class="fail-text">{{ state.failed.reply }}</div>
            <div class="fail-row">
              <span class="fail-hint">⚠ 发送失败</span>
              <button class="retry" @click="retry">重试</button>
            </div>
          </div>
        </div>

        <div v-if="state.sending" class="msg agent">
          <DigitalHuman class="message-human" :style="chosenStyle" small />
          <div class="bubble typing">
            <span class="dots"><i></i><i></i><i></i></span>
            面试官正在思考
          </div>
        </div>

        <!-- 结束态:报告入口 -->
        <div v-if="state.finished" id="done-card" class="done">
          <div class="done-icon">✓</div>
          <div class="done-text">
            <b>面试已完成</b>
            感谢你的参与。系统会基于本次回答生成评估，报告页会显示实际生成状态。
          </div>
          <router-link class="done-btn" :to="`/admin/reports/${interviewId}`">
            查看报告进度与结果 →
          </router-link>
          <router-link
            v-if="jobId"
            class="done-link"
            :to="{ path: '/match', query: { job: jobId } }"
          >查看简历评审单(人岗匹配)→</router-link>
        </div>
      </template>
    </main>

    <footer class="inputbar" v-if="!showPicker && !(state.error && !state.messages.length)">
      <textarea
        ref="inputRef"
        v-model="state.input"
        :disabled="state.finished || state.sending || state.loading || !!state.error"
        :placeholder="inputPlaceholder"
        rows="1"
        @input="autoGrow"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button class="send" :disabled="!canSend" @click="send" title="发送(Enter)">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12.6 2-12.6 2z" fill="currentColor" />
        </svg>
      </button>
    </footer>
  </div>
</template>

<script>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { interviews } from '../api'
import { getInterviewToken } from '../access'
import DigitalHuman from '../components/DigitalHuman.vue'
import { useSpeech } from '../composables/useSpeech'

const PHASE_TEXT = {
  created: '未开始',
  opening: '开场中',
  probing: '专业考察',
  behavioral: '行为面试',
  candidate_qa: '反向提问',
  closing: '收尾中',
  finished: '已完成',
}

const STYLES = [
  { key: 'pro', name: '陈工 · 严谨技术官', desc: '更关注原理、边界与可验证细节', voice: { pitch: 0.9, rate: 1.0 } },
  { key: 'friendly', name: '林姐 · 亲和 HR', desc: '鼓励式提问，帮助你完整表达', voice: { pitch: 1.2, rate: 1.05 } },
  { key: 'pressure', name: '高老师 · 压力面', desc: '从质疑角度追问关键细节', voice: { pitch: 0.85, rate: 1.1 } },
]

const VOICE_BY_STYLE = Object.fromEntries(STYLES.map((s) => [s.key, s.voice]))

const MAX_GROW_PX = 120

function newRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export default {
  name: 'InterviewView',
  components: { DigitalHuman },
  setup() {
    const route = useRoute()
    const interviewId = Number(route.params.id)
    const accessToken = getInterviewToken(interviewId)
    const jobId = ref(0)
    const chatBox = ref(null)
    const inputRef = ref(null)
    const speech = useSpeech()

    const state = reactive({
      loading: true,
      error: '',
      finished: false,
      sending: false,
      input: '',
      messages: [],
      progress: {},
      failed: null,
    })

    const chosenStyle = ref('pro')
    const starting = ref(false)
    const showPicker = ref(false)
    const openingRequestId = ref(newRequestId())

    const hasProgress = computed(() => !!state.progress.phase)
    const phaseKey = computed(() => (state.progress.phase || '').toLowerCase())
    const phaseText = computed(() => PHASE_TEXT[phaseKey.value] || state.progress.phase)
    const asked = computed(() => state.progress.total_questions || 0)
    const total = computed(() => state.progress.max_total_q || 15)
    const progressPercent = computed(() =>
      Math.min(100, Math.round((asked.value / total.value) * 100))
    )
    const styleName = computed(
      () => STYLES.find((s) => s.key === chosenStyle.value)?.name || ''
    )
    const personaName = computed(() => styleName.value.split(' · ').join('·'))

    const canSend = computed(
      () =>
        state.input.trim() &&
        !state.sending &&
        !state.finished &&
        !state.loading &&
        !state.failed
    )

    const inputPlaceholder = computed(() => {
      if (state.finished) return '面试已结束'
      if (state.sending) return '面试官正在出题…'
      if (state.failed) return '上一条回答发送失败，点击「重试」或重新输入'
      return '输入你的回答，Enter 发送，Shift+Enter 换行'
    })

    function say(text) {
      speech.speak(text, VOICE_BY_STYLE[chosenStyle.value] || {})
    }

    function scrollBottom() {
      nextTick(() => {
        if (chatBox.value) {
          const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
          chatBox.value.scrollTo({
            top: chatBox.value.scrollHeight,
            behavior: reduceMotion ? 'auto' : 'smooth',
          })
        }
      })
    }

    function autoGrow() {
      const el = inputRef.value
      if (!el) return
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, MAX_GROW_PX) + 'px'
    }

    function focusInput() {
      nextTick(() => inputRef.value && inputRef.value.focus())
    }

    async function boot() {
      if (!accessToken) {
        state.error = '当前浏览器没有这场面试的访问凭证,请从岗位页重新上传简历进入'
        state.loading = false
        return
      }
      try {
        const s = await interviews.state(interviewId, accessToken)
        state.progress = s.progress
        const full = await interviews.get(interviewId, accessToken)
        chosenStyle.value = full.style || 'pro'
        jobId.value = full.job_id || 0
        const msgs = await interviews.messages(interviewId, accessToken)
        state.messages = msgs.map((m) => ({
          role: m.role,
          text: m.text,
          dimension: m.dimension,
        }))
        if (s.status === 'finished') state.finished = true
        if (msgs.length === 0) {
          if (full.style) {
            // 风格已在「简历分析页」选定 → 不再重复弹选择器,直接开场
            await pickAndStart()
          } else {
            // 旧数据无风格 → 先选风格,不自动生成开场白
            showPicker.value = true
          }
        }
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
        scrollBottom()
        if (!showPicker.value) {
          if (location.hash === '#done-card') {
            nextTick(() =>
              document.getElementById('done-card')?.scrollIntoView({
                block: 'center',
                behavior: 'auto',
              })
            )
          } else {
            focusInput()
          }
        }
      }
    }

    // 选择器里点「开始面试」:请求开场白
    async function pickAndStart() {
      if (starting.value) return
      starting.value = true
      state.error = ''
      try {
        const turn = await interviews.message(
          interviewId,
          null,
          openingRequestId.value,
          accessToken
        )
        state.progress = turn.progress
        state.messages.push({
          role: 'agent',
          text: turn.agent_question,
          dimension: turn.dimension || turn.progress?.current_dimension,
        })
        if (turn.finished) state.finished = true
        showPicker.value = false
        say(turn.agent_question)
        focusInput()
      } catch (e) {
        state.error = e.message
      } finally {
        starting.value = false
      }
    }

    // 一次逻辑发送固定 requestId；网络失败重试时复用，避免服务端重复推进。
    async function deliver(reply, requestId = newRequestId()) {
      state.sending = true
      state.failed = null
      state.messages.push({ role: 'candidate', text: reply })
      scrollBottom()
      try {
        const turn = await interviews.message(interviewId, reply, requestId, accessToken)
        state.progress = turn.progress
        state.messages.push({
          role: 'agent',
          text: turn.agent_question,
          dimension: turn.dimension || turn.progress?.current_dimension,
        })
        say(turn.agent_question)
        if (turn.finished) state.finished = true
      } catch (e) {
        state.messages.pop() // 撤回展示,由失败卡片接管
        state.error = ''
        state.failed = { reply, requestId }
      } finally {
        state.sending = false
        scrollBottom()
      }
    }

    async function send() {
      const reply = state.input.trim()
      if (!canSend.value) return
      state.input = ''
      autoGrow()
      await deliver(reply)
      focusInput()
    }

    async function retry() {
      const failed = state.failed
      if (!failed || state.sending) return
      await deliver(failed.reply, failed.requestId)
    }

    async function retryBoot() {
      if (!accessToken || state.loading) return
      state.error = ''
      state.loading = true
      await boot()
    }

    onMounted(boot)

    return {
      interviewId,
      jobId,
      accessToken,
      chatBox,
      inputRef,
      state,
      speech,
      STYLES,
      chosenStyle,
      starting,
      showPicker,
      hasProgress,
      phaseKey,
      phaseText,
      asked,
      total,
      progressPercent,
      styleName,
      personaName,
      canSend,
      inputPlaceholder,
      autoGrow,
      pickAndStart,
      send,
      retry,
      retryBoot,
    }
  },
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  max-width: 760px;
  margin: 0 auto;
  background: #fff;
  border-radius: 0;
  box-shadow: 0 8px 40px rgba(30, 60, 110, 0.1);
  overflow: hidden;
}

/* ---------- 顶栏 ---------- */
.topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px 9px;
  border-bottom: 1px solid #eef1f5;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  z-index: 2;
}

.interviewer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.interviewer :deep(.dh) {
  padding: 2px;
}

.who {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.who b {
  font-size: 14px;
  color: #1a3a63;
}

.who span {
  font-size: 11px;
  color: #8a97a8;
}

.top-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chip {
  font-size: 12px;
  color: #5f6b7a;
  background: #f2f5f9;
  padding: 4px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.chip.phase {
  color: #1a73e8;
  background: #e8f1fd;
  font-weight: 600;
}

.chip.phase.finished {
  color: #1a7f37;
  background: #e8f5e9;
}

.chip.phase.closing,
.chip.phase.candidate_qa {
  color: #b26a00;
  background: #fff3e0;
}

.voice-btn {
  border: 1px solid #dde3ec;
  background: #fff;
  border-radius: 999px;
  width: 44px;
  height: 44px;
  font-size: 15px;
  cursor: pointer;
  flex-shrink: 0;
}

.voice-btn:hover {
  border-color: #1a73e8;
}

.progressbar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 3px;
  background: #eef1f5;
}

.progressbar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 0 999px 999px 0;
  transition: width 0.5s ease;
}

/* ---------- 聊天区 ---------- */
.chat {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  background:
    radial-gradient(circle at 12% 8%, rgba(26, 115, 232, 0.06), transparent 42%),
    radial-gradient(circle at 88% 92%, rgba(79, 156, 249, 0.08), transparent 45%),
    #f7f9fc;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.picker-chat {
  align-items: center;
  justify-content: center;
}

.picker {
  width: 100%;
  max-width: 560px;
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 16px;
  padding: 26px 24px;
  box-shadow: 0 6px 22px rgba(30, 60, 110, 0.08);
  text-align: center;
  animation: msgIn 0.3s ease both;
}

.picker h1 {
  font-size: 19px;
  color: #1a3a63;
  margin-bottom: 6px;
}

.picker .sub {
  font-size: 13px;
  color: #6b7a8d;
  margin-bottom: 18px;
}

.styles {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 18px;
}

.style {
  position: relative;
  border: 2px solid #eef1f5;
  border-radius: 14px;
  padding: 14px 8px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.style input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.style.on {
  border-color: #1a73e8;
  box-shadow: 0 4px 14px rgba(26, 115, 232, 0.18);
}

.style b {
  display: block;
  font-size: 12.5px;
  color: #2c3e50;
  margin: 8px 0 4px;
}

.style span {
  font-size: 11px;
  color: #6b7a8d;
  line-height: 1.5;
  display: block;
}

.picker .primary {
  width: 100%;
  border: none;
  border-radius: 10px;
  background: var(--color-primary);
  color: #fff;
  min-height: 44px;
  padding: 12px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: none;
}

.picker .primary:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

.center {
  margin: auto;
  color: #9aa5b1;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.error {
  color: #e5533d;
}

.center.error {
  max-width: 360px;
  flex-direction: column;
  text-align: center;
  line-height: 1.6;
}

.center.error p {
  margin: 0;
}

.error-actions,
.picker-error {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.picker-error {
  margin-top: 14px;
}

.return-link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  color: #1768cf;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

/* ---------- 消息 ---------- */
.msg {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 85%;
  animation: msgIn 0.2s ease both;
}

@keyframes msgIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.msg.agent {
  align-self: flex-start;
}

.msg.candidate {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 3px 8px rgba(26, 115, 232, 0.3);
}

.message-human {
  flex-shrink: 0;
}

.bubble-wrap {
  min-width: 0;
}

.message-dimension {
  display: block;
  margin: 0 0 4px 3px;
  color: #6b7a8d;
  font-size: 11px;
  line-height: 1.4;
}

.msg.candidate .message-dimension {
  margin-right: 3px;
  text-align: right;
}

.bubble {
  padding: 11px 15px;
  border-radius: 14px;
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
}

.msg.agent .bubble {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(30, 60, 110, 0.05);
}

.msg.candidate .bubble {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 3px 10px rgba(26, 115, 232, 0.25);
}

/* 打字动画:三点跳动 */
.typing {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8a97a8;
  font-size: 13px;
}

.dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #4f9cf9;
  animation: bounce 1.2s infinite ease-in-out;
}

.dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

/* ---------- 发送失败卡片 ---------- */
.fail-card {
  background: #fff6f4;
  border: 1px solid #f3c6bd;
  border-radius: 14px 4px 14px 14px;
  padding: 10px 14px;
  max-width: 100%;
}

.fail-text {
  font-size: 13px;
  color: #7a4a40;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 8px;
}

.fail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.fail-hint {
  font-size: 12px;
  color: #e5533d;
}

.retry {
  border: none;
  border-radius: 999px;
  background: #e5533d;
  color: #fff;
  font-size: 12px;
  min-height: 44px;
  padding: 4px 14px;
  cursor: pointer;
}

.retry:hover {
  background: #d0442e;
}

/* ---------- 完成卡片 ---------- */
.done {
  margin-top: 8px;
  padding: 22px;
  text-align: center;
  background: linear-gradient(180deg, #f0faf1, #fff);
  border: 1px solid #cde9d2;
  border-radius: 16px;
  animation: msgIn 0.3s ease both;
}

.done-icon {
  width: 40px;
  height: 40px;
  margin: 0 auto 10px;
  border-radius: 50%;
  background: #1a7f37;
  color: #fff;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(26, 127, 55, 0.3);
}

.done-text {
  font-size: 14px;
  color: #3f5a45;
  line-height: 1.7;
  margin-bottom: 14px;
}

.done-text b {
  display: block;
  font-size: 16px;
  color: #1a7f37;
}

.done-btn {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  text-decoration: none;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  padding: 10px 22px;
  border-radius: 999px;
  box-shadow: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.done-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(26, 115, 232, 0.4);
}

.done-link {
  display: block;
  margin-top: 12px;
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.done-link:hover {
  text-decoration: underline;
}

/* ---------- 输入区 ---------- */
.inputbar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 14px 16px calc(14px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid #eef1f5;
  background: #fff;
}

.inputbar textarea {
  flex: 1;
  resize: none;
  border: 1px solid #dde3ec;
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 16px;
  line-height: 1.5;
  outline: none;
  font-family: inherit;
  min-height: 46px;
  max-height: 120px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.inputbar textarea:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.15);
}

.send {
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.32);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.send:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(26, 115, 232, 0.42);
}

.send:active:not(:disabled) {
  transform: scale(0.94);
}

.send:disabled {
  background: #c6d4e8;
  cursor: not-allowed;
  box-shadow: none;
}

.err {
  margin-top: 10px;
  font-size: 13px;
  color: #e5533d;
}

/* ---------- 移动端 ---------- */
@media (max-width: 640px) {
  .page {
    box-shadow: none;
  }

  .topbar {
    gap: 6px;
    padding: 6px 10px 7px;
  }

  .progress-chips {
    gap: 4px;
    flex-wrap: nowrap;
  }

  .progress-chips .dimension {
    display: none;
  }

  .chip {
    padding: 4px 7px;
    font-size: 11px;
  }

  .voice-btn {
    width: 44px;
    height: 44px;
  }

  .chat {
    padding: 16px 12px;
  }

  .msg {
    max-width: 92%;
  }

  .styles {
    grid-template-columns: 1fr;
  }

  .inputbar {
    padding: 10px 10px calc(10px + env(safe-area-inset-bottom, 0px));
  }
}

@media (max-width: 400px) {
  .interviewer {
    gap: 6px;
  }

  .who span {
    display: none;
  }

  .who b {
    font-size: 13px;
  }

  .top-right {
    gap: 4px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .picker,
  .msg,
  .done,
  .progressbar-fill,
  .inputbar textarea,
  .send,
  .done-btn,
  .dots i {
    animation: none;
    transition: none;
  }
}
</style>
