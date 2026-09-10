<template>
  <div class="report">
    <header class="topbar">
      <router-link class="brand" to="/">
        <span class="brand-mark">面</span>
        <span>面评家 · 竞争力报告</span>
      </router-link>
      <router-link class="back" to="/">返回岗位大厅</router-link>
    </header>

    <div v-if="!state.report" class="empty panel" aria-live="polite">
      <span class="state-icon" aria-hidden="true">{{ state.error ? '!' : '…' }}</span>
      <h1>{{ state.error ? '暂时无法查看报告' : '竞争力报告准备中' }}</h1>
      <p>{{ state.error || statusText }}</p>
      <button v-if="state.canRetry" class="primary" :disabled="state.evaluating" @click="runEvaluate">
        {{ state.evaluating ? '正在提交…' : '生成或重试报告' }}
      </button>
      <button v-if="state.error && !state.canRetry && !state.blocked" class="primary"
        :disabled="state.loading" @click="load">重新加载状态</button>
      <router-link v-if="state.status === 'not_started' && !state.canRetry"
        :to="`/interview/${id}`">返回面试</router-link>
    </div>

    <div v-else-if="state.report" class="content">
      <div class="report-heading">
        <div>
          <p class="eyebrow">模拟面试结果</p>
          <h1>个人竞争力报告</h1>
        </div>
      </div>

      <!-- 总分 + 建议 -->
      <section class="panel score-panel">
        <div class="score">
          <span class="score-label">综合表现</span>
          <span class="num">{{ state.report.summary_score ?? '—' }}</span>
          <span class="unit">{{ state.report.summary_score == null ? '暂不计算完整总分' : '/ 100' }}</span>
        </div>
        <div class="suggestion">
          <span class="section-kicker">AI 评估结论</span>
          <p class="summary">{{ state.report.suggestion }}</p>
          <p v-if="state.report.coverage" class="muted">
            有效评分覆盖 {{ state.report.coverage.assessed }} / {{ state.report.coverage.total }} 项
            （{{ state.report.coverage.percent }}%）。
            <span v-if="state.report.summary_score == null && state.report.assessed_score != null">
              已评估部分得分 {{ state.report.assessed_score }} / 100，仅代表已覆盖部分。
            </span>
          </p>
          <p v-else class="legacy-note">历史报告：尚未按消息编号逐条核验证据，请结合下方回答证据理解分数。</p>
        </div>
      </section>

      <div class="assessment-grid">
        <!-- 雷达图 -->
        <section class="panel chart-panel">
          <h2>维度得分</h2>
          <div v-if="hasCompleteScores" ref="chartEl" class="chart"></div>
          <p v-else class="muted">部分维度尚未取得有效评分，暂不绘制完整雷达图。请查看右侧的考察状态。</p>
        </section>

        <!-- 维度明细 + 证据 -->
        <section class="panel">
          <h2>维度明细与证据</h2>
          <div v-for="d in state.report.dimensions" :key="d.name" class="dim">
            <div class="dim-head">
              <span class="dim-name">{{ d.name }}</span>
              <span class="dim-score">{{ dimensionLabel(d) }}</span>
            </div>
            <ul>
              <li v-for="(ev, i) in d.evidence" :key="i">
                「{{ ev }}」
                <button v-if="d.evidence_refs?.[i]" class="source-link"
                  :disabled="state.evidenceLoading" @click="showEvidence(d.evidence_refs[i])">
                  查看回答 #{{ d.evidence_refs[i].message_id }}
                </button>
              </li>
              <li v-if="!d.evidence || !d.evidence.length" class="muted">该维度无有效回答证据</li>
            </ul>
          </div>
        </section>
      </div>

      <section v-if="state.evidence || state.evidenceError" class="panel evidence-panel">
        <h2>原始问答</h2>
        <p v-if="state.evidenceError">{{ state.evidenceError }}</p>
        <template v-else>
          <p>消息 #{{ state.evidence.message_id }} · {{ state.evidence.dimension || '未标注维度' }}</p>
          <p><strong>面试官：</strong>{{ state.evidence.question }}</p>
          <pre>{{ state.evidence.text }}</pre>
        </template>
      </section>

      <div class="insight-grid">
        <!-- 亮点 -->
        <section class="panel insight-card strength-card">
          <h2><span aria-hidden="true">✓</span> 已展现的优势</h2>
          <ul>
            <li v-for="(s, i) in state.report.strengths" :key="i">{{ s }}</li>
          </ul>
        </section>

        <!-- 待改进短板 -->
        <section class="panel insight-card risk-card">
          <h2><span aria-hidden="true">!</span> 优先补强项</h2>
          <ul>
            <li v-for="(r, i) in state.report.risks" :key="i">{{ r }}</li>
          </ul>
        </section>

        <!-- 提升建议 -->
      </div>

      <section class="panel action-panel">
        <div class="action-heading">
          <span class="section-kicker">下一步行动</span>
          <h2>把反馈变成可执行的练习</h2>
        </div>
        <ol>
          <li v-for="(q, i) in state.report.next_step_questions" :key="i">
            <span>{{ i + 1 }}</span><p>{{ q }}</p>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { interviews } from '../api'
import { getInterviewToken } from '../access'
import { init as initChart } from '../lib/echarts'

export default {
  name: 'ReportView',
  setup() {
    const route = useRoute()
    const id = Number(route.params.id)
    const accessToken = getInterviewToken(id)
    const chartEl = ref(null)
    let chart = null
    let disposed = false
    let pollTimer = null
    const state = reactive({
      report: null,
      error: '',
      evaluating: false,
      loading: false,
      status: 'loading',
      canRetry: false,
      blocked: false,
      evidence: null,
      evidenceError: '',
      evidenceLoading: false,
    })
    const statusText = computed(() => ({
      loading: '正在读取报告状态…',
      not_started: state.canRetry ? '面试已结束，可以生成评估报告。' : '面试尚未结束，完成后即可生成报告。',
      pending: '评估任务已提交，正在等待生成。你可以稍后回来查看。',
      running: '正在分析本次回答，页面会自动更新。',
      failed: '报告生成失败，可以重试。',
      ready: '报告已生成。',
    }[state.status] || '正在读取报告状态…'))
    const hasCompleteScores = computed(() => {
      const dims = state.report?.dimensions || []
      return dims.length > 0 && dims.every((d) => Number.isFinite(d.score))
    })

    function dimensionLabel(dimension) {
      if (dimension.status === 'not_assessed') return '未考察'
      if (dimension.score == null) return '证据不足，暂不评分'
      return `${dimension.score} / 10`
    }

    async function showEvidence(ref) {
      if (state.evidenceLoading) return
      state.evidenceLoading = true
      state.evidenceError = ''
      try {
        const messages = await interviews.messages(id, accessToken)
        if (disposed) return
        const index = messages.findIndex((m) => m.id === ref.message_id && m.role === 'candidate')
        if (index < 0) throw new Error('未找到对应的候选人回答')
        state.evidence = {
          message_id: ref.message_id, text: messages[index].text,
          dimension: messages[index].dimension,
          question: messages.slice(0, index).reverse().find((m) => m.role === 'agent')?.text || '无提问记录',
        }
      } catch (e) {
        state.evidenceError = `无法读取原话：${e.message}`
      } finally {
        state.evidenceLoading = false
      }
    }

    function renderChart() {
      const dims = state.report?.dimensions || []
      const el = chartEl.value
      chart?.dispose()
      chart = null
      if (disposed || !el || !hasCompleteScores.value) return
      chart = initChart(el)
      chart.setOption({
        radar: {
          indicator: dims.map((d) => ({ name: d.name, max: 10 })),
          radius: '65%',
        },
        tooltip: {},
        series: [
          {
            type: 'radar',
            data: [
              {
                value: dims.map((d) => d.score),
                name: '得分',
                areaStyle: { opacity: 0.2 },
              },
            ],
          },
        ],
      })
    }

    function clearPoll() {
      if (pollTimer != null) window.clearTimeout(pollTimer)
      pollTimer = null
    }

    async function applyStatus(data) {
      if (disposed) return
      state.report = data.report || null
      state.status = data.status || (data.report ? 'ready' : 'not_started')
      state.canRetry = !!data.can_retry
      state.error = data.error || ''
      state.blocked = false
      clearPoll()
      if (state.report) {
        await nextTick()
        renderChart()
      } else if (['pending', 'running'].includes(state.status)) {
        pollTimer = window.setTimeout(load, 2000)
      }
    }

    function showRequestError(error) {
      if (disposed) return
      state.error = error.message || '读取失败，请重试。'
      state.blocked = [401, 403, 404].includes(error.status)
      state.canRetry = false
    }

    async function load() {
      if (disposed || state.loading) return
      clearPoll()
      state.error = ''
      if (!accessToken) {
        state.blocked = true
        state.error = '当前浏览器没有这份报告的访问凭证,请从对应面试页进入'
        return
      }
      state.loading = true
      try {
        await applyStatus(await interviews.report(id, accessToken))
      } catch (e) {
        showRequestError(e)
      } finally {
        state.loading = false
      }
    }

    async function runEvaluate() {
      if (disposed || state.evaluating || !accessToken || !state.canRetry) return
      clearPoll()
      state.evaluating = true
      state.error = ''
      try {
        await applyStatus(await interviews.evaluate(id, accessToken))
      } catch (e) {
        showRequestError(e)
      } finally {
        state.evaluating = false
      }
    }

    function onResize() {
      chart?.resize()
    }

    onMounted(() => {
      load()
      window.addEventListener('resize', onResize)
    })

    onBeforeUnmount(() => {
      disposed = true
      clearPoll()
      window.removeEventListener('resize', onResize)
      chart?.dispose()
      chart = null
    })

    return { id, chartEl, state, load, runEvaluate, statusText, hasCompleteScores, dimensionLabel, showEvidence }
  },
}
</script>

<style scoped>
.report {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 20px 56px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  color: var(--text-strong, #17233c);
  font-size: 16px;
  font-weight: 750;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  background: var(--brand-600, #2563eb);
  color: #fff;
  font-size: 15px;
}

.back {
  font-size: 14px;
  color: var(--brand-700, #1d4ed8);
  text-decoration: none;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}

.panel {
  background: #fff;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--radius-lg, 14px);
  padding: 22px;
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(15, 23, 42, 0.05));
}

.panel h2 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #2c3e50;
}

.report-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.report-heading h1 {
  color: var(--text-strong, #17233c);
  font-size: clamp(24px, 4vw, 32px);
  letter-spacing: -0.02em;
}

.eyebrow,
.section-kicker,
.score-label {
  color: var(--brand-700, #1d4ed8);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.score-panel {
  display: flex;
  align-items: stretch;
  gap: 28px;
  margin-bottom: 18px;
  border-top: 3px solid var(--brand-600, #2563eb);
}

.score {
  min-width: 150px;
  display: flex;
  flex-wrap: wrap;
  align-content: center;
  align-items: baseline;
  gap: 0 6px;
  border-right: 1px solid var(--border, #dfe6ef);
}

.score-label {
  flex-basis: 100%;
  margin-bottom: 4px;
}

.score .num {
  font-size: 52px;
  font-weight: 800;
  color: var(--brand-700, #1d4ed8);
}

.score .unit {
  color: #9aa5b1;
  font-size: 14px;
}

.suggestion {
  flex: 1;
  color: var(--text-strong, #17233c);
  min-width: 0;
}

.suggestion .summary {
  margin-top: 6px;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.65;
}

.suggestion .muted {
  margin-top: 8px;
  font-size: 13px;
}

.legacy-note {
  margin-top: 10px;
  padding: 9px 11px;
  border-left: 3px solid var(--warning-500, #d97706);
  background: var(--warning-50, #fffbeb);
  color: var(--warning-800, #92400e);
  font-size: 12px;
  line-height: 1.6;
}

.assessment-grid {
  display: grid;
  grid-template-columns: minmax(280px, 5fr) minmax(0, 7fr);
  gap: 18px;
  margin-bottom: 18px;
}

.chart {
  height: 320px;
}

.dim {
  padding: 13px 0;
  border-top: 1px solid var(--border-subtle, #edf1f6);
}

.dim:first-of-type { border-top: 0; padding-top: 0; }

.dim-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.dim-name {
  font-weight: 600;
  font-size: 14px;
}

.dim-score {
  color: var(--brand-700, #1d4ed8);
  font-weight: 700;
}

ul {
  padding-left: 18px;
}

li {
  font-size: 13px;
  line-height: 1.75;
  color: var(--text, #334155);
}

.muted {
  color: #69798a;
}

.source-link {
  border: 0;
  background: transparent;
  color: var(--brand-700, #1d4ed8);
  cursor: pointer;
  min-height: 36px;
  padding: 6px 8px;
}

.evidence-panel { margin-bottom: 16px; }
.evidence-panel pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}

.insight-card h2 {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strength-card h2 { color: var(--success-700, #15803d); }
.risk-card h2 { color: var(--warning-800, #92400e); }

.action-panel {
  display: grid;
  grid-template-columns: minmax(190px, 0.8fr) minmax(0, 1.6fr);
  gap: 28px;
  margin-bottom: 0;
}

.action-heading h2 { margin-top: 7px; font-size: 19px; line-height: 1.45; }
.action-panel ol { list-style: none; padding: 0; }
.action-panel li { display: flex; gap: 12px; padding: 11px 0; border-top: 1px solid var(--border-subtle, #edf1f6); }
.action-panel li:first-child { border-top: 0; padding-top: 0; }
.action-panel li > span { display: grid; flex: 0 0 26px; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: var(--brand-50, #eff6ff); color: var(--brand-700, #1d4ed8); font-weight: 700; }
.action-panel li p { margin: 1px 0 0; color: var(--text, #334155); line-height: 1.7; }

.empty {
  text-align: center;
  max-width: 620px;
  margin: 80px auto 0;
  padding: 42px 28px;
  color: var(--text-muted, #64748b);
}

.empty h1 { margin: 14px 0 8px; color: var(--text-strong, #17233c); font-size: 22px; }
.empty p { line-height: 1.7; }

.state-icon {
  display: grid;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-50, #eff6ff);
  color: var(--brand-700, #1d4ed8);
  font-weight: 800;
}

.empty .primary {
  margin-top: 16px;
  border: none;
  min-height: 44px;
  border-radius: var(--radius-md, 10px);
  background: var(--brand-600, #2563eb);
  color: #fff;
  padding: 10px 22px;
  font-size: 14px;
  cursor: pointer;
}

@media (max-width: 720px) {
  .report { padding: 16px 14px 40px; }
  .topbar { margin-bottom: 22px; }
  .brand { font-size: 14px; }
  .brand-mark { width: 32px; height: 32px; }
  .back { font-size: 13px; }
  .report-heading { align-items: flex-start; }
  .panel { padding: 18px; }
  .score-panel { flex-direction: column; gap: 18px; }
  .score { min-width: 0; border-right: 0; border-bottom: 1px solid var(--border, #dfe6ef); padding-bottom: 14px; }
  .score .num { font-size: 48px; }
  .assessment-grid,
  .insight-grid,
  .action-panel { grid-template-columns: 1fr; }
  .chart { height: 280px; }
  .action-panel { gap: 16px; }
  .source-link { min-height: 44px; }
}
</style>
