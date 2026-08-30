<template>
  <div class="comparison">
    <header class="topbar">
      <div class="brand">面评家 · 候选人横向对比</div>
      <a class="back" href="/admin">← 返回后台</a>
    </header>

    <div v-if="state.error" class="empty">{{ state.error }}</div>
    <div v-else-if="state.groups.length" class="content">
      <p class="hint">按岗位分组,展示已完成面试的候选人在各考察维度的得分(深色 = 该列最高分)。</p>

      <section v-for="g in state.groups" :key="g.job_id" class="panel">
        <h2>#{{ g.job_id }} {{ g.job_title }}</h2>
        <table>
          <thead>
            <tr>
              <th>候选人</th>
              <th v-for="d in g.dimensions" :key="d">{{ d }}</th>
              <th>总分</th>
              <th>建议</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in g.candidates" :key="c.interview_id">
              <td class="name">{{ c.candidate_name || '—' }}</td>
              <td
                v-for="(s, i) in c.scores"
                :key="i"
                :class="{ top: s === g.dimBest[i] }"
              >
                {{ s != null ? s : '—' }}
              </td>
              <td class="score" :class="{ top: c.summary_score === g.sumBest }">
                {{ c.summary_score != null ? c.summary_score : '—' }}
              </td>
              <td>{{ c.suggestion }}</td>
              <td><a :href="`/admin/interview/${c.interview_id}`">报告</a></td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <div v-else class="empty">还没有已完成的面试,先去后台发起面试。</div>
  </div>
</template>

<script>
import { onMounted, reactive } from 'vue'
import { interviews } from '../api'

export default {
  name: 'ComparisonView',
  setup() {
    const state = reactive({ groups: [], error: '' })

    // 为每个分组补齐每列最高分,用于高亮
    function withBest(groups) {
      return groups.map((g) => {
        const dimBest = g.dimensions.map((_, i) =>
          Math.max(...g.candidates.map((c) => c.scores[i] ?? -1))
        )
        const sumBest = Math.max(...g.candidates.map((c) => c.summary_score ?? -1))
        return { ...g, dimBest, sumBest }
      })
    }

    async function load() {
      state.error = ''
      try {
        const data = await interviews.comparison()
        state.groups = withBest(data.groups || [])
      } catch (e) {
        state.error = `加载失败:${e.message}`
      }
    }

    onMounted(load)
    return { state }
  },
}
</script>

<style scoped>
.comparison {
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

.back {
  font-size: 14px;
  color: #1a73e8;
  text-decoration: none;
}

.hint {
  font-size: 13px;
  color: #5f6b7a;
  margin-bottom: 16px;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 16px;
}

.panel h2 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #2c3e50;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  text-align: center;
  padding: 8px 10px;
  border-bottom: 1px solid #eef1f5;
}

th {
  color: #5f6b7a;
  font-weight: 600;
}

td.name {
  text-align: left;
  font-weight: 600;
}

td.score {
  font-weight: 700;
}

td.top {
  color: #1a73e8;
  background: #f2f6ff;
  font-weight: 700;
  border-radius: 6px;
}

td a {
  color: #1a73e8;
  text-decoration: none;
}

.empty {
  text-align: center;
  padding: 60px 0;
  color: #7f8c8d;
}
</style>
