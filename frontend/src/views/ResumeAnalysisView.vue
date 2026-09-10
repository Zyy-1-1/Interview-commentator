<template>
  <div class="apply">
    <header class="topbar">
      <router-link class="back" to="/">← 返回岗位大厅</router-link>
      <div class="steps" aria-label="申请流程">
        <span class="step done">岗位</span>
        <span class="sep" aria-hidden="true">/</span>
        <span class="step" :class="{ done: !!state.cand, on: !state.cand }">简历解析</span>
        <span class="sep" aria-hidden="true">/</span>
        <span class="step" :class="{ on: !!state.cand }">模拟面试</span>
      </div>
    </header>

    <main class="apply-flow" :class="{ 'has-candidate': state.cand }">
      <!-- 岗位信息 -->
      <section class="panel job-card" v-if="state.job">
        <p class="eyebrow">应聘岗位</p>
        <h1>{{ state.job.title }}</h1>
        <p class="company">{{ state.job.company || '面评家官方岗位' }}</p>
        <div class="dims" v-if="state.job.dimensions">
          <span class="chip" v-for="d in state.job.dimensions" :key="d.name">
            {{ d.name }}
          </span>
        </div>
        <p class="job-note">面试将围绕以上岗位维度展开。</p>
      </section>

      <div class="apply-content">
        <section v-if="state.jobError" class="panel state-card" role="alert">
          <p class="eyebrow">暂时无法继续</p>
          <h2>该岗位目前不可开始模拟面试</h2>
          <p class="sub">{{ state.jobError }}</p>
          <router-link class="secondary-link" to="/">返回岗位大厅</router-link>
        </section>

        <!-- 第一步:上传简历 -->
        <section
          v-else-if="!state.cand"
          class="panel upload-zone"
          :class="{ hover: dragHover }"
          @dragover.prevent="dragHover = true"
          @dragleave="dragHover = false"
          @drop.prevent="onDrop"
        >
          <div class="up-icon" aria-hidden="true">⌁</div>
          <p class="eyebrow">第 2 步 · 简历解析</p>
          <h2>上传简历，准备开始陪练</h2>
          <p class="sub">支持 PDF、DOCX、Markdown、TXT，单个文件最大 10 MB。可拖拽到此处或点击选择。</p>
          <p class="trust-note">原文件仅用于本次解析，解析结束后会立即从服务器删除。</p>
          <button class="primary" :disabled="!canUpload" @click="$refs.file.click()">
            {{ state.uploading ? '正在解析简历…' : '选择简历文件' }}
          </button>
          <input ref="file" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onFile" />
          <p v-if="state.uploading" class="dots-line" aria-live="polite">
            正在读取和解析简历 <span class="dots"><i></i><i></i><i></i></span>
          </p>
          <div v-if="state.uploadError" class="error-action" role="alert">
            <p class="err">{{ state.uploadError }}</p>
            <button class="text-btn" :disabled="state.uploading" @click="$refs.file.click()">重新选择文件</button>
          </div>
        </section>

        <!-- 第二步:简历档案 + 选择面试官风格并开始 -->
        <template v-else>
          <section class="panel profile-card">
            <div class="profile-head">
              <div>
                <p class="eyebrow">简历概览</p>
                <h2>已完成解析</h2>
              </div>
              <button class="ghost" @click="reupload">换一份简历</button>
            </div>
            <p class="cand-name">{{ state.cand.name || '未识别姓名' }}</p>
            <div v-if="brief" class="brief">
              <div v-if="brief.school" class="row"><span>学校</span><b>{{ brief.school }}</b></div>
              <div v-if="brief.major" class="row"><span>专业</span><b>{{ brief.major }}</b></div>
              <div v-if="brief.experience" class="row"><span>经历</span><b>{{ brief.experience }}</b></div>
              <div v-if="brief.skills" class="row"><span>技能</span><b>{{ brief.skills }}</b></div>
            </div>
            <p v-else class="sub">未提取到完整的结构化信息，你仍可继续进行模拟面试。</p>
            <router-link class="match-link" :to="{ path: '/match', query: { job: jobId } }">
              查看这份简历与岗位的匹配评审单 →
            </router-link>
          </section>

          <section class="panel start-zone">
            <p class="eyebrow">第 3 步 · 模拟面试</p>
            <h2>选择 AI 面试官风格</h2>
            <p class="sub">不同风格会改变提问与追问方式；这是一场练习，不替代真实招聘结果。</p>
            <div class="styles">
              <label v-for="s in STYLES" :key="s.key" class="style" :class="{ on: style === s.key }">
                <input type="radio" :value="s.key" v-model="style" />
                <DigitalHuman class="style-human" :style="s.key" />
                <b>{{ s.name }}</b>
                <span>{{ s.desc }}</span>
              </label>
            </div>
            <button class="primary big" :disabled="state.starting" @click="start">
              {{ state.starting ? '正在创建面试…' : `以「${styleName}」开始模拟面试` }}
            </button>
            <div v-if="state.startError" class="error-action" role="alert">
              <p class="err">{{ state.startError }}</p>
              <router-link class="text-btn" to="/">返回岗位大厅</router-link>
            </div>
          </section>
        </template>
      </div>
    </main>
  </div>
</template>

<script>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { candidates, interviews, jobs } from '../api'
import { storeCandidate, storeInterviewToken } from '../access'
import DigitalHuman from '../components/DigitalHuman.vue'

const STYLES = [
  {
    key: 'pro',
    name: '严谨技术官 · 陈工',
    desc: '更关注原理、边界与可验证细节',
  },
  {
    key: 'friendly',
    name: '亲和 HR · 林姐',
    desc: '鼓励式提问，帮助你放松并完整表达',
  },
  {
    key: 'pressure',
    name: '压力面试官 · 高老师',
    desc: '从质疑角度追问简历中的关键细节',
  },
]

export default {
  name: 'ResumeAnalysisView',
  components: { DigitalHuman },
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
      jobError: '',
      uploadError: '',
      startError: '',
    })
    const dragHover = ref(false)
    const style = ref('pro')

    const canUpload = computed(
      () => !!state.job && !state.jobError && !state.uploading
    )

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
      const suffix = `.${(file.name || '').split('.').pop().toLowerCase()}`
      if (!['.pdf', '.docx', '.txt', '.md'].includes(suffix)) {
        state.uploadError = '文件格式不支持，请选择 PDF、DOCX、Markdown 或 TXT 文件。'
        return
      }
      if (file.size > 10 * 1024 * 1024) {
        state.uploadError = '文件超过 10 MB，请压缩或选择更小的简历文件后重试。'
        return
      }
      state.uploading = true
      state.uploadError = ''
      try {
        state.cand = await candidates.upload(file)
        storeCandidate(state.cand)
      } catch (e) {
        state.uploadError = e.message || '简历解析失败，请重新选择文件后重试。'
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
      state.uploadError = ''
      state.startError = ''
    }

    async function start() {
      state.starting = true
      state.startError = ''
      try {
        const token = state.cand.access_token
        const iv = await interviews.create(jobId, state.cand.id, style.value, token)
        storeInterviewToken(iv.id, token)
        router.push(`/interview/${iv.id}`)
      } catch (e) {
        state.startError = e.message || '创建面试失败，请稍后重试。'
        state.starting = false
      }
    }

    onMounted(async () => {
      try {
        state.job = await jobs.get(jobId)
        if (!state.job.dimensions || !state.job.dimensions.length) {
          state.jobError = '该岗位尚未完成岗位维度配置，请返回岗位大厅选择其他岗位。'
        }
      } catch (e) {
        state.jobError = e.message || '岗位信息加载失败，请返回岗位大厅后重试。'
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
      canUpload,
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
  max-width: 1120px;
  margin: 0 auto;
  padding: 22px 24px 56px;
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
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.steps {
  display: flex;
  align-items: center;
  gap: 9px;
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

.apply-flow {
  display: grid;
  grid-template-columns: minmax(250px, 0.72fr) minmax(0, 1.28fr);
  align-items: start;
  gap: 18px;
}

.apply-content {
  min-width: 0;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 8px 24px rgba(30, 60, 110, 0.06);
  margin-bottom: 16px;
}

.eyebrow {
  margin: 0 0 7px;
  color: #6680a2;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.job-card {
  position: sticky;
  top: 18px;
  overflow: hidden;
}

.job-card h1 {
  margin: 0;
  font-size: 23px;
  line-height: 1.35;
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
  font-size: 12px;
  color: #1a73e8;
  background: #e8f1fd;
  padding: 5px 10px;
  border-radius: 999px;
}

.job-note {
  margin: 16px 0 0;
  padding-top: 14px;
  border-top: 1px solid #eef1f5;
  color: #6b7a8d;
  font-size: 13px;
  line-height: 1.6;
}

/* 上传区 */
.upload-zone {
  text-align: center;
  min-height: 352px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 42px 28px;
  border: 2px dashed #cdd9ea;
  background: linear-gradient(150deg, #fbfdff, #f4f8fd);
  transition: border-color 0.15s ease, background 0.15s ease;
}

.upload-zone.hover {
  border-color: #1a73e8;
  background: #eff6ff;
}

.up-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  margin-bottom: 12px;
  border: 1px solid #cdddf1;
  border-radius: 14px;
  background: #fff;
  color: #1a73e8;
  font-size: 30px;
  font-weight: 700;
}

.upload-zone h2 {
  margin: 0 0 8px;
  font-size: 20px;
  color: #2c3e50;
}

.sub {
  margin: 0;
  font-size: 13px;
  color: #6b7a8d;
  line-height: 1.8;
}

.trust-note {
  max-width: 520px;
  margin: 14px 0 0;
  color: #4d6788;
  font-size: 12px;
  line-height: 1.6;
}

button.primary {
  margin-top: 18px;
  border: none;
  border-radius: 10px;
  background: var(--color-primary);
  color: #fff;
  min-height: 44px;
  padding: 11px 30px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: none;
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
  min-height: 44px;
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

.error-action {
  margin-top: 12px;
}

.text-btn,
.secondary-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  border: 0;
  background: transparent;
  color: #1768cf;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}

.text-btn:disabled {
  color: #9aa5b1;
  cursor: not-allowed;
}

.state-card {
  text-align: center;
  padding: 44px 28px;
}

.state-card h2 {
  margin: 0 0 8px;
}

.state-card .secondary-link {
  margin-top: 18px;
  padding: 0 16px;
  border: 1px solid #c9d8e9;
  border-radius: 999px;
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
  margin-top: 0;
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
  margin: 18px 0 10px;
  font-size: 18px;
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

.profile-card .sub {
  margin-top: 14px;
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
  margin-bottom: 8px;
}

.start-zone > .sub {
  margin-bottom: 18px;
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
  min-height: 214px;
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

.style :deep(.style-human.dh) {
  margin: 0 auto 10px;
  padding: 3px;
  animation: none;
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
  margin: 0;
  font-size: 13px;
  color: #e5533d;
}

@media (max-width: 820px) {
  .apply {
    padding: 18px 16px 42px;
  }

  .apply-flow {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .job-card {
    position: static;
  }

  .styles {
    grid-template-columns: 1fr;
  }

  .style {
    min-height: 0;
    display: grid;
    grid-template-columns: 64px minmax(0, 1fr);
    column-gap: 12px;
    text-align: left;
    align-items: center;
  }

  .style :deep(.style-human.dh) {
    grid-row: span 2;
    margin: 0;
  }

  .style b,
  .style span {
    grid-column: 2;
  }

  .style b {
    margin: 0 0 4px;
  }
}

@media (max-width: 480px) {
  .topbar {
    align-items: flex-start;
  }

  .steps {
    width: 100%;
    justify-content: space-between;
    gap: 4px;
    font-size: 11px;
  }

  .panel {
    padding: 20px;
  }

  .upload-zone {
    min-height: 330px;
    padding: 32px 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .upload-zone,
  .style {
    transition: none;
  }

  .dots i {
    animation: none;
  }
}
</style>
