// 真实 Vue 组件和模板的离线回归；内存 DOM/API/图表用于验证条件渲染和重试。
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const test = require('node:test')
const Vue = require('vue')
const { parse } = require('vue/compiler-sfc')

const reportTimers = new Map()
let timerSequence = 0
global.window = {
  addEventListener() {}, removeEventListener() {},
  setTimeout(callback) { reportTimers.set(++timerSequence, callback); return timerSequence },
  clearTimeout(id) { reportTimers.delete(id) },
}
global.location = { hash: '' }

function makeNode(type, text = '') {
  return Vue.markRaw({
    type, text, props: {}, children: [], parent: null,
    addEventListener() {}, removeEventListener() {}, style: {}, focus() {}, scrollTo() {},
  })
}
const renderer = Vue.createRenderer({
  createElement: (type) => makeNode(type),
  createText: (text) => makeNode('#text', text),
  createComment: (text) => makeNode('#comment', text),
  setText(node, text) { node.text = text },
  setElementText(node, text) { node.text = text; node.children = [] },
  parentNode: (node) => node.parent,
  nextSibling: (node) => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  insert(node, parent, anchor) {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(node)
    else parent.children.splice(index, 0, node)
  },
  remove(node) {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = null
  },
  patchProp(node, key, previous, value) { node.props[key] = value },
  setScopeId() {},
})

function mount(file, overrides) {
  const { descriptor } = parse(readFileSync(resolve(__dirname, '../src', file), 'utf8'))
  // 只执行受信任的本仓库源码，显式替换 import，避免调用真实服务。
  const script = descriptor.script.content.replace(/^import .*$/gm, '').replace('export default', 'return')
  const charts = []
  const bindings = {
    ...Vue,
    useRoute: () => ({ params: { id: '1', jobId: '1' } }),
    useRouter: () => ({ push() {} }),
    getInterviewToken: () => 'synthetic-token',
    storeInterviewToken() {},
    initChart(el) {
      const chart = {
        el, disposed: false, option: null,
        setOption(option) { this.option = option },
        dispose() { this.disposed = true },
        resize() {}, clear() {},
      }
      charts.push(chart)
      return chart
    },
    ...overrides,
  }
  const component = Function(...Object.keys(bindings), script)(...Object.values(bindings))
  component.render = Vue.compile(descriptor.template.content)
  const root = makeNode('root')
  const app = renderer.createApp(component)
  app.component('router-link', { setup(_, { slots }) { return () => Vue.h('a', slots.default?.()) } })
  const vm = app.mount(root)
  return { root, vm, charts, unmount: () => app.unmount() }
}
function chartNodes(node) {
  const matched = String(node.props.class || '').split(' ').includes('chart')
  return [...(matched ? [node] : []), ...node.children.flatMap(chartNodes)]
}
async function settle() {
  for (let i = 0; i < 5; i++) await Vue.nextTick()
}
const dimensions = [{ name: 'Python', score: 8 }, { name: 'Communication', score: 6 }]
const result = { overall: 70, dimension_scores: dimensions, highlights: [], gaps: [] }
const report = {
  summary_score: 70, dimensions: dimensions.map((d) => ({ ...d, evidence: [] })),
  strengths: [], risks: [], next_step_questions: [],
}
const jobs = { get: async () => ({ title: 'Synthetic job', dimensions }) }

test('匹配完成后绘图，换简历后销毁旧图并绑定新容器', async (t) => {
  const page = mount('views/ResumeAnalysisView.vue', { jobs, candidates: { match: async () => result } })
  t.after(page.unmount)
  await settle()
  page.vm.state.cand = { id: 1, access_token: 'test' }
  await page.vm.loadMatch()
  await settle()
  assert.equal(page.charts.length, 1)
  assert.equal(page.charts[0].el, chartNodes(page.root)[0])
  page.vm.reupload()
  await settle()
  assert.equal(page.charts[0].disposed, true)
  page.vm.state.cand = { id: 2, access_token: 'test' }
  await page.vm.loadMatch()
  await settle()
  assert.equal(page.charts.length, 2)
  assert.notEqual(page.charts[0].el, page.charts[1].el)
  assert.equal(page.charts[1].el, chartNodes(page.root)[0])
})

test('匹配失败后重试可以显示图表', async (t) => {
  let calls = 0
  const page = mount('views/ResumeAnalysisView.vue', { jobs, candidates: { match: async () => {
    if (calls++ === 0) throw new Error('Temporary failure')
    return result
  } } })
  t.after(page.unmount)
  await settle()
  page.vm.state.cand = { id: 1, access_token: 'test' }
  await page.vm.loadMatch()
  assert.equal(page.vm.match, null)
  await page.vm.loadMatch()
  await settle()
  assert.equal(page.vm.state.error, '')
  assert.equal(page.charts.length, 1)
})

test('换简历后忽略旧请求迟到的结果', async (t) => {
  let complete
  const page = mount('views/ResumeAnalysisView.vue', { jobs, candidates: {
    match: () => new Promise((resolve) => { complete = resolve }),
  } })
  t.after(page.unmount)
  await settle()
  page.vm.state.cand = { id: 1, access_token: 'test' }
  const pending = page.vm.loadMatch()
  page.vm.reupload()
  complete(result)
  await pending
  await settle()
  assert.equal(page.vm.match, null)
  assert.equal(page.charts.length, 0)
})

test('报告重试成功后清除错误并显示报告与图表', async (t) => {
  const page = mount('admin/ReportView.vue', { interviews: {
    report: async () => ({ status: 'failed', report: null, error: 'Temporary failure', can_retry: true }),
    evaluate: async () => ({ report }),
  } })
  t.after(page.unmount)
  await settle()
  assert.ok(page.vm.state.error)
  await page.vm.runEvaluate()
  await settle()
  assert.equal(page.vm.state.error, '')
  assert.equal(page.vm.state.report.summary_score, 70)
  assert.equal(page.charts.length, 1)
  assert.equal(page.charts[0].el, chartNodes(page.root)[0])
})

function visibleText(node) {
  return node.text + node.children.map(visibleText).join(' ')
}

test('覆盖不完整时显示未考察状态，不用零分绘制雷达图', async (t) => {
  const partial = {
    ...report, schema_version: 2, summary_score: null, assessed_score: 80,
    coverage: { assessed: 1, total: 2, percent: 50 },
    dimensions: [
      { name: 'Python', status: 'scored', score: 8, evidence: [] },
      { name: 'Communication', status: 'not_assessed', score: null, evidence: [] },
    ],
  }
  const page = mount('admin/ReportView.vue', { interviews: { report: async () => ({ report: partial }) } })
  t.after(page.unmount)
  await settle()
  assert.equal(page.charts.length, 0)
  assert.match(visibleText(page.root), /未考察/)
  assert.match(visibleText(page.root), /暂不计算完整总分/)
  assert.equal(page.vm.dimensionLabel(partial.dimensions[1]), '未考察')
})

test('报告证据可以按编号展开对应的原始问答', async (t) => {
  const page = mount('admin/ReportView.vue', { interviews: {
    report: async () => ({ report }),
    messages: async () => [
      { id: 1, role: 'agent', text: 'Explain the decision' },
      { id: 2, role: 'candidate', dimension: 'Python', text: 'Full original answer and details' },
    ],
  } })
  t.after(page.unmount)
  await settle()
  await page.vm.showEvidence({ message_id: 2 })
  await settle()
  assert.match(visibleText(page.root), /Full original answer and details/)
  assert.equal(page.vm.state.evidence.question, 'Explain the decision')
})

test('报告生成中持续查询，成功后停止轮询且不重复发起评估', async (t) => {
  let reads = 0
  let evaluations = 0
  const page = mount('admin/ReportView.vue', { interviews: {
    report: async () => ++reads === 1
      ? { status: 'running', report: null, can_retry: false }
      : { status: 'ready', report },
    evaluate: async () => { evaluations++; return { status: 'pending' } },
  } })
  t.after(page.unmount)
  await settle()
  assert.match(visibleText(page.root), /正在分析本次回答/)
  assert.equal(reportTimers.size, 1)
  await page.vm.runEvaluate()
  assert.equal(evaluations, 0)
  const poll = [...reportTimers.values()][0]
  await poll()
  await settle()
  assert.equal(page.vm.state.report.summary_score, 70)
  assert.equal(reportTimers.size, 0)
})

test('报告状态的鉴权失败不显示生成按钮', async (t) => {
  let evaluations = 0
  const page = mount('admin/ReportView.vue', { interviews: {
    report: async () => { const e = new Error('凭证无效'); e.status = 401; throw e },
    evaluate: async () => { evaluations++ },
  } })
  t.after(page.unmount)
  await settle()
  await page.vm.runEvaluate()
  assert.equal(page.vm.state.blocked, true)
  assert.equal(evaluations, 0)
  assert.doesNotMatch(visibleText(page.root), /生成或重试报告/)
})

test('离开报告页后清理轮询，迟到响应不再绘图', async () => {
  const page = mount('admin/ReportView.vue', { interviews: {
    report: async () => ({ status: 'pending', report: null }),
  } })
  await settle()
  assert.equal(reportTimers.size, 1)
  page.unmount()
  assert.equal(reportTimers.size, 0)
  let finish
  const late = mount('admin/ReportView.vue', { interviews: {
    report: () => new Promise((resolve) => { finish = resolve }),
  } })
  late.unmount()
  finish({ report })
  await settle()
  assert.equal(late.charts.length, 0)
})

test('面试结束页显示报告进度入口，不提前宣布报告生成成功', async (t) => {
  const page = mount('candidate/InterviewView.vue', {
    DigitalHuman: { render: () => null },
    useSpeech: () => ({ supported: false, state: {}, speak() {} }),
    interviews: {
      state: async () => ({ status: 'finished', progress: { phase: 'CLOSING' } }),
      get: async () => ({ style: 'pro' }),
      messages: async () => [{ role: 'agent', text: '面试结束，谢谢参与' }],
    },
  })
  t.after(page.unmount)
  await settle()
  assert.match(visibleText(page.root), /查看报告进度与结果/)
  assert.doesNotMatch(visibleText(page.root), /报告已生成/)
})

test('刷新报告页可以直接加载已有结果', async (t) => {
  const page = mount('admin/ReportView.vue', { interviews: { report: async () => ({ report }) } })
  t.after(page.unmount)
  await settle()
  assert.equal(page.vm.state.report.summary_score, 70)
  assert.equal(page.charts.length, 1)
})
