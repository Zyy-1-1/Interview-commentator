<template>
  <div class="submit">
    <header class="topbar">
      <router-link class="back" to="/">← 返回岗位大厅</router-link>
    </header>

    <div class="panel">
      <h1>发布招聘信息</h1>
      <p class="sub">
        提交后由面评家官方审核,通过后即上架岗位大厅,应聘者可直接与 AI 面试官模拟面试。
      </p>

      <label>公司名称</label>
      <input v-model="form.company" placeholder="如:某某科技" maxlength="100" />

      <label>岗位名称</label>
      <input v-model="form.title" placeholder="如:Python 后端开发" maxlength="200" />

      <label>岗位 JD(职责与要求,越详细 AI 拆解的考察维度越准)</label>
      <textarea
        v-model="form.jdText"
        rows="10"
        placeholder="粘贴岗位 JD 文本:工作职责、任职要求、技术栈、加分项…"
      ></textarea>

      <button class="primary" :disabled="!canSubmit" @click="submit">
        {{ state.busy ? '提交中…' : '提交审核' }}
      </button>

      <div v-if="state.done" class="ok-card">
        ✓ 「{{ state.doneTitle }}」已提交,等待官方审核通过后会出现在岗位大厅。
        <router-link to="/">回大厅</router-link>
      </div>
      <p v-if="state.error" class="err">{{ state.error }}</p>
    </div>
  </div>
</template>

<script>
import { computed, reactive } from 'vue'
import { jobs } from '../api'

export default {
  name: 'JobSubmitView',
  setup() {
    const form = reactive({ company: '', title: '', jdText: '' })
    const state = reactive({ busy: false, error: '', done: false, doneTitle: '' })

    const canSubmit = computed(
      () => form.title.trim() && form.jdText.trim().length >= 10 && !state.busy
    )

    async function submit() {
      if (!canSubmit.value) return
      state.busy = true
      state.error = ''
      try {
        const j = await jobs.create(form.title.trim(), form.jdText.trim(), form.company.trim())
        state.done = true
        state.doneTitle = j.title
        form.company = ''
        form.title = ''
        form.jdText = ''
      } catch (e) {
        state.error = e.message
      } finally {
        state.busy = false
      }
    }

    return { form, state, canSubmit, submit }
  },
}
</script>

<style scoped>
.submit {
  max-width: 640px;
  margin: 0 auto;
  padding: 20px;
}

.topbar {
  margin-bottom: 14px;
}

.back {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 24px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
}

h1 {
  font-size: 20px;
  color: #1a3a63;
  margin-bottom: 6px;
}

.sub {
  font-size: 13px;
  color: #6b7a8d;
  line-height: 1.7;
  margin-bottom: 14px;
}

label {
  display: block;
  font-size: 13px;
  color: #5f6b7a;
  margin: 14px 0 5px;
}

input,
textarea {
  width: 100%;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

textarea {
  resize: vertical;
  line-height: 1.6;
}

input:focus,
textarea:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.15);
}

button.primary {
  width: 100%;
  margin-top: 18px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  padding: 12px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

button.primary:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

.ok-card {
  margin-top: 16px;
  background: #eef8ef;
  border: 1px solid #cde9d2;
  color: #1a7f37;
  font-size: 14px;
  padding: 12px 14px;
  border-radius: 10px;
}

.ok-card a {
  color: #1a7f37;
}

.err {
  margin-top: 12px;
  font-size: 13px;
  color: #e5533d;
}
</style>
