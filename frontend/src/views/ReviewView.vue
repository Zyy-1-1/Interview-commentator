<template>
  <div class="review">
    <h1 class="page-title">官方审核 · 岗位审核台</h1>

    <!-- 口令门 -->
    <div v-if="!state.authed" class="gate panel">
      <h1>官方审核入口</h1>
      <p class="sub">请输入审核口令(由部署方在环境变量 REVIEW_PASSPHRASE 配置)</p>
      <input
        v-model="state.pass"
        type="password"
        placeholder="审核口令"
        @keydown.enter="authed"
      />
      <button class="primary" :disabled="!state.pass.trim() || state.loading" @click="authed">
        {{ state.loading ? '校验中…' : '进入' }}
      </button>
      <p v-if="state.error" class="err">{{ state.error }}</p>
    </div>

    <!-- 审核队列 -->
    <div v-else class="panel">
      <div class="tabs">
        <button :class="{ on: tab === 'pending' }" @click="switchTab('pending')">
          待审核 {{ tab === 'pending' ? `(${list.length})` : '' }}
        </button>
        <button :class="{ on: tab === 'all' }" @click="switchTab('all')">全部岗位</button>
        <button class="logout" @click="logout">退出</button>
      </div>

      <p v-if="state.loading" class="tip">加载中…</p>
      <p v-else-if="!list.length" class="tip">
        {{ tab === 'pending' ? '没有待审核的岗位 🎉' : '还没有任何岗位' }}
      </p>
      <article v-for="j in list" :key="j.id" class="job">
        <div class="job-head">
          <div>
            <b>{{ j.title }}</b>
            <span class="company">{{ j.company || '(未填公司)' }}</span>
            <span class="badge" :class="j.status">{{ statusText(j.status) }}</span>
          </div>
          <span class="jid">#{{ j.id }}</span>
        </div>
        <p class="jd">{{ j.jd_text }}</p>
        <div class="actions" v-if="j.status === 'pending'">
          <input
            v-model="notes[j.id]"
            placeholder="审核意见(驳回时建议填写)"
            maxlength="200"
          />
          <button class="ok" :disabled="busyId" @click="decide(j, true)">✓ 通过上架</button>
          <button class="no" :disabled="busyId" @click="decide(j, false)">✕ 驳回</button>
        </div>
        <p v-else-if="j.review_note" class="note">审核意见:{{ j.review_note }}</p>
      </article>

      <p v-if="state.error && state.authed" class="err">{{ state.error }}</p>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { jobs } from '../api'

const STATUS_TEXT = { pending: '待审核', approved: '已上架', rejected: '已驳回' }

export default {
  name: 'ReviewView',
  setup() {
    const state = reactive({
      pass: '',
      authed: false,
      loading: false,
      error: '',
      jobs: [],
    })
    const tab = ref('pending')
    const notes = reactive({})
    const busyId = ref(null)

    const list = computed(() =>
      tab.value === 'pending'
        ? state.jobs.filter((j) => j.status === 'pending')
        : state.jobs
    )
    const statusText = (s) => STATUS_TEXT[s] || s

    async function load() {
      state.loading = true
      state.error = ''
      try {
        state.jobs = await jobs.list('all', state.pass)
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function authed() {
      state.loading = true
      state.error = ''
      try {
        await jobs.auth(state.pass)
        state.authed = true
      } catch (e) {
        state.authed = false
        state.error = e.message
        return
      } finally {
        state.loading = false
      }
      await load()
    }

    function switchTab(t) {
      tab.value = t
    }

    function logout() {
      state.authed = false
      state.pass = ''
      state.jobs = []
    }

    async function decide(j, approve) {
      busyId.value = j.id
      state.error = ''
      try {
        const updated = await jobs.review(state.pass, j.id, approve, notes[j.id] || null)
        // 原位更新
        const i = state.jobs.findIndex((x) => x.id === updated.id)
        if (i >= 0) state.jobs[i] = updated
        notes[j.id] = ''
      } catch (e) {
        if (e.message.includes('口令')) {
          state.authed = false
          state.error = '口令错误,请重新输入'
        } else {
          state.error = e.message
        }
      } finally {
        busyId.value = null
      }
    }

    onMounted(() => {
      if (state.authed) load()
    })

    return {
      state,
      tab,
      notes,
      busyId,
      list,
      statusText,
      authed,
      switchTab,
      logout,
      decide,
    }
  },
}
</script>

<style scoped>
.review {
  max-width: 760px;
}

.page-title {
  font-size: 17px;
  color: #1a3a63;
  margin-bottom: 16px;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 22px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
}

.gate {
  max-width: 420px;
  margin: 60px auto 0;
  text-align: center;
}

.gate h1 {
  font-size: 19px;
  color: #1a3a63;
  margin-bottom: 8px;
}

.sub {
  font-size: 13px;
  color: #6b7a8d;
  margin-bottom: 16px;
}

.gate input {
  width: 100%;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.gate input:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.15);
}

button.primary {
  width: 100%;
  margin-top: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  padding: 11px;
  font-size: 14px;
  cursor: pointer;
}

button.primary:disabled {
  background: #c6d4e8;
  cursor: not-allowed;
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  position: relative;
}

.tabs button {
  border: 1px solid #dde3ec;
  background: #f7f9fc;
  border-radius: 999px;
  padding: 6px 16px;
  font-size: 13px;
  color: #5f6b7a;
  cursor: pointer;
}

.tabs button.on {
  background: #e8f1fd;
  border-color: #1a73e8;
  color: #1a73e8;
  font-weight: 600;
}

.tabs .logout {
  position: absolute;
  right: 0;
  border: none;
  background: none;
  color: #9aa5b1;
}

.job {
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.job-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.job-head b {
  font-size: 15px;
  color: #2c3e50;
}

.company {
  font-size: 12px;
  color: #8a97a8;
  margin-left: 8px;
}

.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 999px;
  margin-left: 8px;
  background: #f2f5f9;
  color: #5f6b7a;
}

.badge.pending {
  background: #fff3e0;
  color: #b26a00;
}

.badge.approved {
  background: #e8f5e9;
  color: #1a7f37;
}

.badge.rejected {
  background: #fdecea;
  color: #e5533d;
}

.jid {
  font-size: 12px;
  color: #9aa5b1;
}

.jd {
  font-size: 13px;
  color: #5f6b7a;
  line-height: 1.7;
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
  background: #f7f9fc;
  border-radius: 8px;
  padding: 10px 12px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.actions input {
  flex: 1;
  border: 1px solid #dde3ec;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 13px;
  outline: none;
}

.actions button {
  border: none;
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 13px;
  cursor: pointer;
  color: #fff;
  white-space: nowrap;
}

.actions .ok {
  background: #1a7f37;
}

.actions .no {
  background: #e5533d;
}

.actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.note {
  margin-top: 8px;
  font-size: 12px;
  color: #8a97a8;
}

.tip {
  text-align: center;
  color: #9aa5b1;
  font-size: 14px;
  padding: 30px 0;
}

.err {
  margin-top: 10px;
  font-size: 13px;
  color: #e5533d;
}

.gate .err {
  text-align: center;
}
</style>
