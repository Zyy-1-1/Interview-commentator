<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="dot">🎙</span> 面评家
      </div>
      <div class="progress" v-if="state.progress.current_dimension">
        <span class="chip">当前维度:{{ state.progress.current_dimension }}</span>
        <span class="chip">已问 {{ state.progress.total_questions }}/{{ state.progress.max_total_q }}</span>
      </div>
    </header>

    <main class="chat" ref="chatBox">
      <div v-if="state.loading" class="center">正在连接面试官…</div>
      <div v-else-if="state.error" class="center error">{{ state.error }}</div>
      <template v-else>
        <div v-for="(m, i) in state.messages" :key="i" class="msg" :class="m.role">
          <div class="avatar" v-if="m.role === 'agent'">AI</div>
          <div class="bubble">{{ m.text }}</div>
        </div>
        <div v-if="state.sending" class="msg agent">
          <div class="avatar">AI</div>
          <div class="bubble typing">面试官正在思考…</div>
        </div>
        <div v-if="state.finished" class="done">
          面试已结束,感谢你的参与!你的个人竞争力报告已生成,可返回查看评估结果。
        </div>
      </template>
    </main>

    <footer class="inputbar">
      <textarea
        v-model="state.input"
        :disabled="state.finished || state.sending || state.loading"
        placeholder="输入你的回答,Enter 发送,Shift+Enter 换行"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button :disabled="!canSend" @click="send">发送</button>
    </footer>
  </div>
</template>

<script>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { interviews } from '../api'

export default {
  name: 'InterviewView',
  setup() {
    const route = useRoute()
    const interviewId = Number(route.params.id)
    const chatBox = ref(null)

    const state = reactive({
      loading: true,
      error: '',
      finished: false,
      sending: false,
      input: '',
      messages: [],
      progress: {},
    })

    const canSend = computed(
      () =>
        state.input.trim() &&
        !state.sending &&
        !state.finished &&
        !state.loading
    )

    function scrollBottom() {
      nextTick(() => {
        if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
      })
    }

    async function boot() {
      try {
        const s = await interviews.state(interviewId)
        state.progress = s.progress
        const msgs = await interviews.messages(interviewId)
        state.messages = msgs.map((m) => ({ role: m.role, text: m.text }))
        // 未开场 → 请求开场白
        if (msgs.length === 0) {
          const turn = await interviews.message(interviewId, null)
          state.messages.push({ role: 'agent', text: turn.agent_question })
          state.progress = turn.progress
        }
        if (s.status === 'finished') state.finished = true
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
        scrollBottom()
      }
    }

    async function send() {
      const reply = state.input.trim()
      if (!reply || state.sending || state.finished) return
      state.sending = true
      state.messages.push({ role: 'candidate', text: reply })
      state.input = ''
      scrollBottom()
      try {
        const turn = await interviews.message(interviewId, reply)
        state.progress = turn.progress
        state.messages.push({ role: 'agent', text: turn.agent_question })
        if (turn.finished) state.finished = true
      } catch (e) {
        state.error = e.message
      } finally {
        state.sending = false
        scrollBottom()
      }
    }

    onMounted(boot)

    return { interviewId, chatBox, state, canSend, send }
  },
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 720px;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 0 24px rgba(0, 0, 0, 0.06);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid #eef1f5;
  background: #fff;
}

.brand {
  font-weight: 700;
  font-size: 18px;
  color: #1a73e8;
}

.progress {
  display: flex;
  gap: 8px;
}

.chip {
  font-size: 12px;
  color: #5f6b7a;
  background: #f2f5f9;
  padding: 4px 10px;
  border-radius: 999px;
}

.chat {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f7f9fc;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.center {
  margin: auto;
  color: #9aa5b1;
  font-size: 14px;
}

.error {
  color: #e5533d;
}

.msg {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 85%;
}

.msg.agent {
  align-self: flex-start;
}

.msg.candidate {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #1a73e8;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bubble {
  padding: 10px 14px;
  border-radius: 14px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
}

.msg.agent .bubble {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-bottom-left-radius: 4px;
}

.msg.candidate .bubble {
  background: #1a73e8;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.typing {
  color: #9aa5b1;
  font-style: italic;
}

.done {
  text-align: center;
  color: #7f8c8d;
  font-size: 14px;
  padding: 16px;
  background: #eef6ee;
  border-radius: 10px;
}

.inputbar {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid #eef1f5;
  background: #fff;
}

.inputbar textarea {
  flex: 1;
  resize: none;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  font-family: inherit;
  height: 46px;
}

.inputbar textarea:focus {
  border-color: #1a73e8;
}

.inputbar button {
  width: 76px;
  border: none;
  border-radius: 10px;
  background: #1a73e8;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.inputbar button:disabled {
  background: #c6d4e8;
  cursor: not-allowed;
}
</style>
