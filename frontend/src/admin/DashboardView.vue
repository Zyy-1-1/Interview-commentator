<template>
  <div class="dashboard">
    <header class="topbar">
      <div class="brand">面评家 · 演示后台</div>
      <div class="nav">
        <a class="goto" href="/admin/comparison">横向对比</a>
        <a
          v-if="firstInterviewId"
          class="goto"
          :href="`/interview/${firstInterviewId}`"
          target="_blank"
          >应聘者面试页</a
        >
      </div>
    </header>

    <div class="layout">
      <!-- 左侧:操作表单 -->
      <section class="panel form-panel">
        <h2>创建岗位(JD)</h2>
        <label>岗位名称</label>
        <input v-model="jobForm.title" placeholder="如:Python 后端开发" />
        <label>JD 描述</label>
        <textarea
          v-model="jobForm.jdText"
          rows="5"
          placeholder="粘贴岗位 JD 文本…"
        ></textarea>
        <button class="primary" :disabled="!jobForm.title || !jobForm.jdText || busy" @click="createJob">
          创建岗位(自动解析维度)
        </button>
        <p v-if="lastJob" class="ok">岗位「{{ lastJob.title }}」已创建,解析出 {{ lastJob.dimCount }} 个考察维度</p>

        <h2 class="mt">上传应聘者简历</h2>
        <input type="file" accept=".pdf,.docx,.doc,.txt,.md" @change="onFileChange" />
        <p v-if="lastCandidate" class="ok">
          已解析简历:{{ lastCandidate.name || '(未识别姓名)' }}
        </p>

        <h2 class="mt">发起模拟面试</h2>
        <label>选择目标岗位</label>
        <select v-model="selJob" :disabled="busy">
          <option v-for="j in jobs" :key="j.id" :value="j.id">
            #{{ j.id }} {{ j.title }}{{ j.dimensions ? '' : '(未完成分析)' }}
          </option>
        </select>
        <label>选择应聘者</label>
        <select v-model="selCandidate" :disabled="busy">
          <option v-for="c in candidates" :key="c.id" :value="c.id">
            #{{ c.id }} {{ c.name || '(未命名)' }}
          </option>
        </select>
        <button class="primary" :disabled="!selJob || !selCandidate || busy" @click="createInterview">
          发起模拟面试
        </button>
        <p v-if="interviewLink" class="ok">
          模拟面试已创建(<b>#{{ newInterviewId }}</b>),面试链接:
          <a :href="interviewLink" target="_blank">{{ interviewLink }}</a>
        </p>

        <p v-if="error" class="err">{{ error }}</p>
      </section>

      <!-- 右侧:面试列表 -->
      <section class="panel list-panel">
        <h2>面试列表</h2>
        <table v-if="interviews.length">
          <thead>
            <tr>
              <th>ID</th>
              <th>岗位</th>
              <th>应聘者</th>
              <th>状态</th>
              <th>总分</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="iv in interviews" :key="iv.id">
              <td>{{ iv.id }}</td>
              <td>{{ iv.job_title }}</td>
              <td>{{ iv.candidate_name || '—' }}</td>
              <td><span class="badge" :class="iv.status">{{ statusText(iv.status) }}</span></td>
              <td>{{ iv.summary_score != null ? iv.summary_score : '—' }}</td>
              <td>
                <a v-if="iv.status === 'finished'" :href="`/admin/interview/${iv.id}`">查看报告</a>
                <a v-else :href="`/interview/${iv.id}`" target="_blank">面试链接</a>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty">暂无面试,先在上面创建岗位并上传简历。</p>
      </section>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, reactive, toRefs } from 'vue'
import { candidates, interviews, jobs } from '../api'

const STATUS_TEXT = {
  created: '未开始',
  opening: '开场中',
  probing: '考察中',
  behavioral: '行为面',
  candidate_qa: '应聘者提问',
  closing: '收尾',
  finished: '已完成',
  timeout: '超时',
}

export default {
  name: 'DashboardView',
  setup() {
    const state = reactive({
      jobs: [],
      candidates: [],
      interviews: [],
      jobForm: { title: '', jdText: '' },
      selJob: null,
      selCandidate: null,
      lastJob: null,
      lastCandidate: null,
      interviewLink: '',
      newInterviewId: null,
      busy: false,
      error: '',
    })

    const statusText = (s) => STATUS_TEXT[s] || s

    // 面试列表按 id 倒序,第一场即为演示时想直接打开的面试
    const firstInterviewId = computed(() => state.interviews[0]?.id ?? null)

    async function loadAll() {
      const [js, cs, ivs] = await Promise.all([
        jobs.list(),
        candidates.list(),
        interviews.list(),
      ])
      state.jobs = js
      state.candidates = cs
      state.interviews = ivs
      state.selJob = state.selJob ?? (js[0] ? js[0].id : null)
      state.selCandidate = state.selCandidate ?? (cs[0] ? cs[0].id : null)
    }

    async function run(fn) {
      state.busy = true
      state.error = ''
      try {
        await fn()
      } catch (e) {
        state.error = e.message
      } finally {
        state.busy = false
      }
    }

    async function createJob() {
      await run(async () => {
        const j = await jobs.create(state.jobForm.title, state.jobForm.jdText)
        state.lastJob = {
          title: j.title,
          dimCount: (j.dimensions || []).length,
        }
        state.jobForm = { title: '', jdText: '' }
        await loadAll()
      })
    }

    async function onFileChange(e) {
      const file = e.target.files[0]
      if (!file) return
      await run(async () => {
        const c = await candidates.upload(file)
        state.lastCandidate = c
        await loadAll()
      })
      e.target.value = ''
    }

    async function createInterview() {
      await run(async () => {
        const iv = await interviews.create(state.selJob, state.selCandidate)
        state.newInterviewId = iv.id
        state.interviewLink = `${location.origin}/interview/${iv.id}`
        await loadAll()
      })
    }

    onMounted(async () => {
      try {
        await loadAll()
      } catch (e) {
        state.error = e.message
      }
    })

    return { state, ...toRefs(state), statusText, firstInterviewId, createJob, onFileChange, createInterview }
  },
}
</script>

<style scoped>
.dashboard {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.brand {
  font-size: 20px;
  font-weight: 700;
  color: #1a73e8;
}

.nav {
  display: flex;
  align-items: center;
  gap: 14px;
}

.goto {
  font-size: 14px;
  color: #1a73e8;
}

.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 18px;
}

.panel h2 {
  font-size: 16px;
  margin-bottom: 10px;
  color: #2c3e50;
}

.panel label {
  display: block;
  font-size: 13px;
  color: #5f6b7a;
  margin: 10px 0 4px;
}

.panel input[type='text'],
.panel input[type='file'],
.panel textarea,
.panel select {
  width: 100%;
  border: 1px solid #dde3ec;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.panel input:focus,
.panel textarea:focus,
.panel select:focus {
  border-color: #1a73e8;
}

.panel textarea {
  resize: vertical;
}

button.primary {
  width: 100%;
  margin-top: 12px;
  border: none;
  border-radius: 8px;
  background: #1a73e8;
  color: #fff;
  padding: 10px;
  font-size: 14px;
  cursor: pointer;
}

button.primary:disabled {
  background: #c6d4e8;
  cursor: not-allowed;
}

.mt {
  margin-top: 20px;
}

.ok {
  margin-top: 10px;
  font-size: 13px;
  color: #1a7f37;
  word-break: break-all;
}

.err {
  margin-top: 10px;
  font-size: 13px;
  color: #e5533d;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid #eef1f5;
}

th {
  color: #5f6b7a;
  font-weight: 600;
}

td a {
  color: #1a73e8;
  text-decoration: none;
}

.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f2f5f9;
  color: #5f6b7a;
}

.badge.finished {
  background: #e8f5e9;
  color: #1a7f37;
}

.badge.created {
  background: #fff3e0;
  color: #b26a00;
}

.empty {
  color: #9aa5b1;
  font-size: 13px;
}
</style>
