<template>
  <div class="report">
    <header class="topbar">
      <div class="brand">面评家 · 竞争力报告 #{{ id }}</div>
      <router-link class="back" to="/">← 返回岗位大厅</router-link>
    </header>

    <div v-if="state.error" class="empty">
      <p>{{ state.error }}</p>
      <button class="primary" :disabled="state.evaluating" @click="runEvaluate">
        {{ state.evaluating ? '评估中…' : '立即生成评估报告' }}
      </button>
    </div>

    <div v-else-if="state.report" class="content">
      <!-- 总分 + 建议 -->
      <section class="panel score-panel">
        <div class="score">
          <span class="num">{{ state.report.summary_score ?? '—' }}</span>
          <span class="unit">{{ state.report.summary_score == null ? '暂不计算完整总分' : '/ 100' }}</span>
        </div>
        <div class="suggestion">
          <p>{{ state.report.suggestion }}</p>
          <p v-if="state.report.coverage" class="muted">
            有效评分覆盖 {{ state.report.coverage.assessed }} / {{ state.report.coverage.total }} 项
            （{{ state.report.coverage.percent }}%）。
            <span v-if="state.report.summary_score == null && state.report.assessed_score != null">
              已评估部分得分 {{ state.report.assessed_score }} / 100，仅代表已覆盖部分。
            </span>
          </p>
          <p v-else class="muted">历史报告：尚未按消息编号逐条核验证据。</p>
        </div>
      </section>

      <div class="grid">
        <!-- 雷达图 -->
        <section class="panel">
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

      <div class="grid">
        <!-- 亮点 -->
        <section class="panel">
          <h2>亮点</h2>
          <ul>
            <li v-for="(s, i) in state.report.strengths" :key="i">{{ s }}</li>
          </ul>
        </section>

        <!-- 待改进短板 -->
        <section class="panel">
          <h2>待改进短板</h2>
          <ul>
            <li v-for="(r, i) in state.report.risks" :key="i">{{ r }}</li>
          </ul>
        </section>

        <!-- 提升建议 -->
        <section class="panel">
          <h2>提升建议</h2>
          <ul>
            <li v-for="(q, i) in state.report.next_step_questions" :key="i">{{ q }}</li>
          </ul>
        </section>
      </div>
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
    const state = reactive({
      report: null,
      error: '',
      evaluating: false,
      evidence: null,
      evidenceError: '',
      evidenceLoading: false,
    })
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
      if (!el || !hasCompleteScores.value) return
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

    async function load() {
      state.error = ''
      if (!accessToken) {
        state.error = '当前浏览器没有这份报告的访问凭证,请从对应面试页进入'
        return
      }
      try {
        const data = await interviews.report(id, accessToken)
        state.report = data.report
        await nextTick()
        renderChart()
      } catch (e) {
        state.error = '报告尚未生成,面试可能未结束或评估失败。'
      }
    }

    async function runEvaluate() {
      if (state.evaluating || !accessToken) return
      state.evaluating = true
      try {
        const data = await interviews.evaluate(id, accessToken)
        state.error = ''
        state.report = data.report
        await nextTick()
        renderChart()
      } catch (e) {
        state.error = `评估失败:${e.message}`
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
      window.removeEventListener('resize', onResize)
      chart?.dispose()
      chart = null
    })

    return { id, chartEl, state, runEvaluate, hasCompleteScores, dimensionLabel, showEvidence }
  },
}
</script>

<style scoped>
.report {
  max-width: 960px;
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

.back {
  font-size: 14px;
  color: #1a73e8;
  text-decoration: none;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 18px;
}

.panel h2 {
  font-size: 15px;
  margin-bottom: 12px;
  color: #2c3e50;
}

.score-panel {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 16px;
}

.score .num {
  font-size: 44px;
  font-weight: 800;
  color: #1a73e8;
}

.score .unit {
  color: #9aa5b1;
  font-size: 14px;
}

.suggestion {
  font-size: 16px;
  color: #2c3e50;
  background: #f2f6ff;
  padding: 6px 14px;
  border-radius: 999px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.chart {
  height: 300px;
}

.dim {
  margin-bottom: 14px;
}

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
  color: #1a73e8;
  font-weight: 700;
}

ul {
  padding-left: 18px;
}

li {
  font-size: 13px;
  line-height: 1.7;
  color: #4b5a6a;
}

.muted {
  color: #69798a;
}

.source-link {
  border: 0;
  background: transparent;
  color: #1a73e8;
  cursor: pointer;
  padding: 2px 4px;
}

.evidence-panel { margin-bottom: 16px; }
.evidence-panel pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; }

.empty {
  text-align: center;
  padding: 60px 0;
  color: #7f8c8d;
}

.empty .primary {
  margin-top: 16px;
  border: none;
  border-radius: 8px;
  background: #1a73e8;
  color: #fff;
  padding: 10px 22px;
  font-size: 14px;
  cursor: pointer;
}
</style>
