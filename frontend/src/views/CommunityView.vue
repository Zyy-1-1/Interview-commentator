<template>
  <div class="community">
    <section class="hero">
      <div>
        <p class="eyebrow">求职者社区</p>
        <h1>真实经验，让准备更有方向</h1>
        <p>交流面经、Offer 选择与求职困惑。匿名参与，保持真诚，也尊重彼此。</p>
      </div>
      <p class="who" v-if="nickname"><span>本次匿名身份</span><b>{{ nickname }}</b></p>
    </section>

    <!-- 发帖框 -->
    <section class="composer">
      <div class="composer-title"><h2>分享你的经历或问题</h2><span>发布后本次会话内昵称保持不变</span></div>
      <label for="community-title">标题</label>
      <input
        id="community-title"
        v-model.trim="form.title"
        class="ctitle"
        type="text"
        maxlength="100"
        placeholder="例如：刚面完后端一面，聊聊项目深挖"
      />
      <label for="community-content">正文</label>
      <textarea
        id="community-content"
        v-model.trim="form.content"
        class="cbody"
        rows="4"
        maxlength="5000"
        placeholder="说说你的面试经历、offer 纠结或想问的问题…"
      ></textarea>
      <div class="composer-foot">
        <span class="hint" :class="{ error: submitError }">{{ submitError || `${form.content.length} / 5000` }}</span>
        <button class="publish" :disabled="submitting || !canPublish" @click="publish">
          {{ submitting ? '发布中…' : '发布内容' }}
        </button>
      </div>
    </section>

    <main class="body">
      <div class="feed-heading"><h2>最新交流</h2><span v-if="state.posts.length">{{ state.posts.length }} 条内容</span></div>
      <p v-if="state.loading" class="tip">加载帖子中…</p>
      <p v-else-if="state.error" class="tip err">{{ state.error }}</p>
      <div v-else-if="!state.posts.length" class="tip">还没有帖子,来发第一帖吧 👆</div>
      <div v-else class="list">
        <article
          v-for="p in state.posts"
          :key="p.id"
          class="post"
          @click="$router.push(`/community/${p.id}`)"
        >
          <div class="post-head">
            <h2 class="ptitle">{{ p.title }}</h2>
            <span class="like-cell" :class="{ mine: p.liked_by_me }">❤ {{ p.likes_count }}</span>
          </div>
          <p class="excerpt">{{ p.content }}</p>
          <div class="post-foot">
            <span class="author">{{ p.author_name }}</span>
            <span class="dot">·</span>
            <span class="time">{{ timeAgo(p.created_at) }}</span>
            <span class="spacer"></span>
            <span class="cm">💬 {{ p.comment_count }}</span>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { community } from '../api'
import { getCommunityToken } from '../access'
import { timeAgo } from '../format'

export default {
  name: 'CommunityView',
  setup() {
    const state = reactive({ posts: [], loading: true, error: '' })
    const form = reactive({ title: '', content: '' })
    const submitting = ref(false)
    const nickname = ref('')

    const canPublish = computed(
      () => form.title.length >= 2 && form.content.length >= 1 && !submitting.value
    )
    const submitError = computed(() => {
      if (form.title && form.title.length < 2) return '标题至少 2 个字'
      return ''
    })

    async function load() {
      state.loading = true
      state.error = ''
      try {
        state.posts = await community.list(getCommunityToken())
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function publish() {
      if (!canPublish.value) return
      submitting.value = true
      state.error = ''
      try {
        await community.create(getCommunityToken(), form.title, form.content)
        form.title = ''
        form.content = ''
        await load()
      } catch (e) {
        state.error = e.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(async () => {
      try {
        const me = await community.me(getCommunityToken())
        nickname.value = me.nickname
      } catch {
        /* 昵称展示失败不阻断列表 */
      }
      load()
    })

    return {
      state,
      form,
      submitting,
      nickname,
      canPublish,
      submitError,
      publish,
      timeAgo,
    }
  },
}
</script>

<style scoped>
.community {
  min-height: 60vh;
  min-width: 0;
}

.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 8px 2px 22px;
}

.hero h1 {
  margin: 5px 0 8px;
  font-size: clamp(24px, 4.4vw, 31px);
  color: var(--text-strong, #17233c);
  letter-spacing: -.02em;
}

.hero p {
  max-width: 620px;
  font-size: 14px;
  color: var(--text-muted, #64748b);
  line-height: 1.7;
}

.hero .eyebrow { color: var(--brand-700, #1d4ed8); font-size: 12px; font-weight: 700; letter-spacing: .08em; }

.hero .who {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  align-items: flex-end;
  padding: 10px 12px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: 10px;
  background: #fff;
  font-size: 12px;
  color: var(--text-muted, #64748b);
}

.hero .who b {
  margin-top: 2px;
  color: var(--brand-700, #1d4ed8);
  font-size: 13px;
}

/* 发帖框 */
.composer {
  background: #fff;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--radius-lg, 14px);
  padding: 18px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(15, 23, 42, .05));
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.composer-title { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 2px; }
.composer-title h2 { color: var(--text-strong, #17233c); font-size: 16px; }
.composer-title span { color: var(--text-muted, #64748b); font-size: 12px; }
.composer label { color: var(--text, #334155); font-size: 12px; font-weight: 650; }

.ctitle,
.cbody {
  width: 100%;
  border: 1px solid var(--border-strong, #c7d2e0);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--text-strong, #17233c);
  font-family: inherit;
  resize: vertical;
}

.ctitle:focus,
.cbody:focus {
  outline: none;
  border-color: #1a73e8;
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  font-size: 12px;
  color: var(--text-muted, #64748b);
}
.hint.error { color: var(--danger-700, #b91c1c); }

.publish {
  min-height: 44px;
  border: none;
  background: var(--brand-600, #2563eb);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 26px;
  border-radius: var(--radius-md, 10px);
  cursor: pointer;
  box-shadow: none;
}

.feed-heading { display: flex; align-items: center; justify-content: space-between; margin: 0 2px 12px; }
.feed-heading h2 { color: var(--text-strong, #17233c); font-size: 17px; }
.feed-heading span { color: var(--text-muted, #64748b); font-size: 12px; }

.publish:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

/* 帖子列表 */
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post {
  background: #fff;
  min-width: 0;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--radius-lg, 14px);
  padding: 18px 20px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.post:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(30, 60, 110, 0.1);
}

.post-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ptitle {
  font-size: 16px;
  color: var(--text-strong, #17233c);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.like-cell {
  font-size: 12.5px;
  color: #9aa5b1;
  white-space: nowrap;
}

.like-cell.mine {
  color: #e5533d;
  font-weight: 600;
}

.excerpt {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text, #334155);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-foot {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8a97a8;
}

.post-foot .author {
  color: var(--brand-700, #1d4ed8);
  font-weight: 650;
}

.post-foot .spacer {
  flex: 1;
}

.tip {
  text-align: center;
  color: #9aa5b1;
  padding: 50px 0;
  font-size: 14px;
}

.tip.err {
  color: #e5533d;
}

@media (max-width: 640px) {
  .hero {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
    padding: 4px 2px 18px;
  }
  .hero .who { align-items: flex-start; width: 100%; }
  .composer { padding: 16px; }
  .composer-title { align-items: flex-start; flex-direction: column; gap: 3px; }
  .ctitle, .cbody { min-width: 0; font-size: 16px; }
  .composer-foot { gap: 12px; }
  .publish { flex: 0 0 auto; }
  .post { padding: 16px; }
  .ptitle { white-space: normal; line-height: 1.45; }
}
</style>
