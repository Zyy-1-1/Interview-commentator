<template>
  <div class="apply">
    <header class="topbar">
      <router-link class="back" to="/">← 返回岗位大厅</router-link>
      <div class="steps">
        <span class="step done">① 选择岗位</span>
        <span class="sep">—</span>
        <span class="step" :class="{ done: !!state.cand, on: !state.cand }">② 上传简历</span>
        <span class="sep">—</span>
        <span class="step" :class="{ on: !!state.cand }">③ 开始模拟面试</span>
      </div>
    </header>

    <!-- 岗位信息 -->
    <section class="panel job-card" v-if="state.job">
      <h1>{{ state.job.title }}</h1>
      <p class="company">{{ state.job.company || '面评家官方岗位' }}</p>
      <div class="dims" v-if="state.job.dimensions">
        <span class="chip" v-for="d in state.job.dimensions" :key="d.name">
          {{ d.name }}
        </span>
      </div>
    </section>

    <!-- 第一步:上传简历 -->
    <section v-if="!state.cand" class="panel upload-zone" :class="{ hover: dragHover }"
      @dragover.prevent="dragHover = true" @dragleave="dragHover = false"
      @drop.prevent="onDrop">
      <div class="up-icon">📄</div>
      <h2>上传你的简历</h2>
      <p class="sub">支持 PDF / DOCX / Markdown / TXT（最大 10 MB）,拖拽或点击选择文件</p>
      <p class="sub">AI 解析简历后,即可选择面试官风格直接开始模拟面试</p>
      <button class="primary" :disabled="state.uploading" @click="$refs.file.click()">
        {{ state.uploading ? '解析中,请稍候…' : '选择简历文件' }}
      </button>
      <input ref="file" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onFile" />
      <p v-if="state.uploading" class="dots-line">
        正在解析简历 <span class="dots"><i></i><i></i><i></i></span>
      </p>
      <p v-if="state.error" class="err">{{ state.error }}</p>
    </section>

    <!-- 第二步:简历档案 + 选择面试官风格并开始 -->
    <template v-else>
      <section class="panel">
        <div class="profile-head">
          <h2>简历档案</h2>
          <button class="ghost" @click="reupload">换一份简历</button>
        </div>
        <p class="cand-name">{{ state.cand.name || '(未识别姓名)' }}</p>
        <div v-if="brief" class="brief">
          <div v-if="brief.school" class="row"><span>学校</span><b>{{ brief.school }}</b></div>
          <div v-if="brief.major" class="row"><span>专业</span><b>{{ brief.major }}</b></div>
          <div v-if="brief.experience" class="row"><span>经历</span><b>{{ brief.experience }}</b></div>
          <div v-if="brief.skills" class="row"><span>技能</span><b>{{ brief.skills }}</b></div>
        </div>
        <router-link class="match-link" :to="{ path: '/match', query: { job: jobId } }">
          想看这份简历与岗位的匹配评审单?前往「简历评审」→
        </router-link>
      </section>

      <section class="panel start-zone">
        <h2>选择你的 AI 面试官</h2>
        <div class="styles">
          <label v-for="s in STYLES" :key="s.key" class="style" :class="{ on: style === s.key }">
            <input type="radio" :value="s.key" v-model="style" />
            <div class="avatar" :style="{ background: s.grad }">{{ s.emoji }}</div>
            <b>{{ s.name }}</b>
            <span>{{ s.desc }}</span>
          </label>
        </div>
        <button class="primary big" :disabled="state.starting" @click="start">
          {{ state.starting ? '创建面试中…' : `以「${styleName}」开始模拟面试 →` }}
        </button>
        <p v-if="state.error" class="err" role="alert">{{ state.error }}</p>
      </section>
    </template>
  </div>
</template>

<script>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { candidates, interviews, jobs } from '../api'
import { storeCandidate, storeInterviewToken } from '../access'

const STYLES = [
  {
    key: 'pro',
    name: '严谨技术官 · 陈工',
    desc: '深挖原理与细节,每个回答至少追一层',
    emoji: '🧑‍💻',
    grad: 'linear-gradient(135deg,#1a73e8,#4f9cf9)',
  },
  {
    key: 'friendly',
    name: '亲和 HR · 林姐',
    desc: '鼓励式提问,帮你放松表达真实水平',
    emoji: '👩‍💼',
    grad: 'linear-gradient(135deg,#2e9e6b,#6fd3a1)',
  },
  {
    key: 'pressure',
    name: '压力面试官 · 高老师',
    desc: '对简历亮点保持怀疑,追问可验证细节',
    emoji: '🧐',
    grad: 'linear-gradient(135deg,#c2410c,#f59e0b)',
  },
]

export default {
  name: 'ResumeAnalysisView',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const jobId = Number(route.params.jobId)
    let disposed = false

    const state = reactive({
      job: null,
      cand: null,
      uploading: false,
      starting: false,
      error: '',
    })
    const dragHover = ref(false)
    const style = ref('pro')

    const styleName = computed(
      () => STYLES.find((s) => s.key === style.value)?.name || ''
    )

    const brief = computed(() => {
      const p = state.cand?.parsed_resume
      if (!p) return null
      const basic = p.basic || {}
      const exp = (p.experience || [])[0]
      return {
        school: basic.school,
        major: basic.major,
        experience: exp ? `${exp.company || ''} · ${exp.role || ''}` : '',
        skills: (p.skills?.programming || []).slice(0, 6).join(' / '),
      }
    })

    async function handleFile(file) {
      if (!file || state.uploading || disposed) return
      state.uploading = true
      state.error = ''
      try {
        state.cand = await candidates.upload(file)
        storeCandidate(state.cand)
      } catch (e) {
        state.error = e.message
      } finally {
        state.uploading = false
      }
    }

    function onFile(e) {
      handleFile(e.target.files[0])
      e.target.value = ''
    }

    function onDrop(e) {
      dragHover.value = false
      handleFile(e.dataTransfer.files[0])
    }

    function reupload() {
      state.cand = null
      state.error = ''
    }

    async function start() {
      state.starting = true
      state.error = ''
      try {
        const token = state.cand.access_token
        const iv = await interviews.create(jobId, state.cand.id, style.value, token)
        storeInterviewToken(iv.id, token)
        router.push(`/interview/${iv.id}`)
      } catch (e) {
        state.error = e.message
        state.starting = false
      }
    }

    onMounted(async () => {
      try {
        state.job = await jobs.get(jobId)
        if (!state.job.dimensions || !state.job.dimensions.length) {
          state.error = '该岗位尚未完成 AI 维度分析,暂不可面试,请换一个岗位'
        }
      } catch (e) {
        state.error = e.message
      }
    })

    onBeforeUnmount(() => {
      disposed = true
    })

    return {
      state,
      jobId,
      dragHover,
      style,
      STYLES,
      styleName,
      brief,
      onFile,
      onDrop,
      reupload,
      start,
    }
  },
}
</script>

<style scoped>
.apply {
  min-height: 100vh;
  max-width: 980px;
  margin: 0 auto;
  padding: 20px 20px 50px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.back {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.steps {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #9aa5b1;
}

.step.on {
  color: #1a73e8;
  font-weight: 600;
}

.step.done {
  color: #1a7f37;
}

.sep {
  color: #dde3ec;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 22px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
  margin-bottom: 16px;
}

.job-card h1 {
  font-size: 21px;
  color: #1a3a63;
}

.company {
  font-size: 13px;
  color: #8a97a8;
  margin: 4px 0 10px;
}

.dims {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 11px;
  color: #1a73e8;
  background: #e8f1fd;
  padding: 3px 10px;
  border-radius: 999px;
}

/* 上传区 */
.upload-zone {
  text-align: center;
  padding: 48px 24px;
  border: 2px dashed #cdd9ea;
  background: #f9fbfe;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.upload-zone.hover {
  border-color: #1a73e8;
  background: #eff6ff;
}

.up-icon {
  font-size: 40px;
  margin-bottom: 8px;
}

.upload-zone h2 {
  font-size: 17px;
  color: #2c3e50;
  margin-bottom: 8px;
}

.sub {
  font-size: 13px;
  color: #6b7a8d;
  line-height: 1.8;
}

button.primary {
  margin-top: 18px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  padding: 11px 30px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

button.primary:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

button.primary.big {
  width: 100%;
  padding: 14px;
  font-size: 16px;
}

button.ghost {
  border: 1px solid #dde3ec;
  background: #fff;
  border-radius: 999px;
  padding: 7px 18px;
  font-size: 13px;
  color: #5f6b7a;
  cursor: pointer;
}

button.ghost:hover {
  border-color: #1a73e8;
  color: #1a73e8;
}

.dots-line {
  margin-top: 14px;
  font-size: 13px;
  color: #8a97a8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.dots {
  display: inline-flex;
  gap: 4px;
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
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-5px); opacity: 1; }
}

/* 简历档案 */
.panel h2 {
  font-size: 15px;
  color: #2c3e50;
  margin-bottom: 12px;
}

.profile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.cand-name {
  font-size: 17px;
  font-weight: 700;
  color: #1a3a63;
  margin-bottom: 10px;
}

.row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 6px 0;
  border-bottom: 1px dashed #eef1f5;
}

.row span {
  width: 40px;
  color: #9aa5b1;
  flex-shrink: 0;
}

.row b {
  color: #4b5a6a;
  font-weight: 500;
  word-break: break-all;
}

.match-link {
  display: inline-block;
  margin-top: 12px;
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.match-link:hover {
  text-decoration: underline;
}

/* 风格选择 */
.start-zone h2 {
  text-align: center;
  margin-bottom: 16px;
}

.styles {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 6px;
}

.style {
  position: relative;
  border: 2px solid #eef1f5;
  border-radius: 14px;
  padding: 18px 12px;
  text-align: center;
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

.style .avatar {
  width: 52px;
  height: 52px;
  margin: 0 auto 10px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
}

.style b {
  display: block;
  font-size: 14px;
  color: #2c3e50;
  margin-bottom: 6px;
}

.style span {
  font-size: 12px;
  color: #6b7a8d;
  line-height: 1.6;
}

.err {
  margin-top: 12px;
  font-size: 13px;
  color: #e5533d;
}

@media (max-width: 820px) {
  .styles {
    grid-template-columns: 1fr;
  }

  .steps {
    display: none;
  }
}
</style>
