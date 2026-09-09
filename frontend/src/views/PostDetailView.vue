<template>
  <div class="detail">
    <div class="crumbs">
      <router-link to="/community">← 返回交流区</router-link>
    </div>

    <p v-if="state.loading" class="tip">加载帖子中…</p>
    <p v-else-if="state.error" class="tip err">{{ state.error }}</p>
    <template v-else-if="post">
      <article class="card">
        <h1 class="ptitle">{{ post.title }}</h1>
        <div class="meta">
          <span class="author">{{ post.author_name }}</span>
          <span class="dot">·</span>
          <span class="time">{{ timeAgo(post.created_at) }}</span>
        </div>
        <p class="content">{{ post.content }}</p>
        <div class="card-foot">
          <button class="like-btn" :class="{ liked: post.liked_by_me }" @click="toggleLike">
            {{ post.liked_by_me ? '❤️ 已赞' : '🤍 点赞' }} · {{ post.likes_count }}
          </button>
          <span class="cm-count">💬 {{ post.comments.length }} 条评论</span>
        </div>
      </article>

      <section class="comments">
        <h2 class="sec-title">全部回复({{ post.comments.length }})</h2>
        <p v-if="!post.comments.length" class="empty">还没有回复,抢个沙发~</p>
        <article v-for="c in post.comments" :key="c.id" class="comment">
          <div class="c-head">
            <span class="author">{{ c.author_name }}</span>
            <span class="time">{{ timeAgo(c.created_at) }}</span>
          </div>
          <p class="c-body">{{ c.content }}</p>
        </article>

        <div class="reply">
          <textarea
            v-model.trim="draft"
            rows="3"
            maxlength="1000"
            placeholder="友善发言,匿名回复…"
          ></textarea>
          <div class="reply-foot">
            <span class="hint" v-if="error">{{ error }}</span>
            <button class="send" :disabled="sending || !draft" @click="send">
              {{ sending ? '发送中…' : '回复' }}
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { community } from '../api'
import { getCommunityToken } from '../access'
import { timeAgo } from '../format'

export default {
  name: 'PostDetailView',
  setup() {
    const route = useRoute()
    const state = reactive({ loading: true, error: '', post: null })
    const draft = ref('')
    const sending = ref(false)
    const error = ref('')

    async function load() {
      state.loading = true
      state.error = ''
      try {
        state.post = await community.get(route.params.id, getCommunityToken())
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function toggleLike() {
      if (!state.post || state.post._liking) return
      state.post._liking = true
      try {
        const r = await community.like(state.post.id, getCommunityToken())
        state.post.liked_by_me = r.liked
        state.post.likes_count = r.likes_count
      } catch (e) {
        error.value = e.message
      } finally {
        state.post._liking = false
      }
    }

    async function send() {
      if (!draft.value || sending.value) return
      sending.value = true
      error.value = ''
      try {
        const c = await community.comment(state.post.id, getCommunityToken(), draft.value)
        state.post.comments.push(c)
        draft.value = ''
      } catch (e) {
        error.value = e.message
      } finally {
        sending.value = false
      }
    }

    onMounted(load)

    const post = computed(() => state.post)
    return { state, post, draft, sending, error, toggleLike, send, timeAgo }
  },
}
</script>

<style scoped>
.detail {
  min-height: 60vh;
}

.crumbs {
  margin: 4px 0 14px;
}

.crumbs a {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.card {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
}

.ptitle {
  font-size: 20px;
  color: #1a3a63;
  line-height: 1.4;
}

.meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #8a97a8;
}

.meta .author {
  color: #7a3ff2;
}

.content {
  margin-top: 14px;
  font-size: 14.5px;
  color: #2c3e50;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.card-foot {
  margin-top: 18px;
  border-top: 1px solid #eef1f5;
  padding-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.like-btn {
  border: 1px solid #dde3ec;
  background: #fff;
  color: #5f6b7a;
  font-size: 13.5px;
  padding: 7px 18px;
  border-radius: 999px;
  cursor: pointer;
}

.like-btn.liked {
  border-color: #f3c1b6;
  background: #fdefec;
  color: #e5533d;
  font-weight: 600;
}

.cm-count {
  font-size: 12.5px;
  color: #9aa5b1;
}

/* 评论 */
.comments {
  margin-top: 18px;
}

.sec-title {
  font-size: 15px;
  color: #1a3a63;
  margin-bottom: 10px;
}

.empty {
  font-size: 13px;
  color: #9aa5b1;
  padding: 18px 0;
}

.comment {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 10px;
}

.c-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.c-head .author {
  color: #7a3ff2;
  font-weight: 600;
}

.c-head .time {
  color: #9aa5b1;
}

.c-body {
  margin-top: 6px;
  font-size: 13.5px;
  color: #2c3e50;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.reply {
  margin-top: 14px;
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
  padding: 12px;
}

.reply textarea {
  width: 100%;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13.5px;
  color: #2c3e50;
  font-family: inherit;
  resize: vertical;
}

.reply textarea:focus {
  outline: none;
  border-color: #1a73e8;
}

.reply-foot {
  margin-top: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  font-size: 12px;
  color: #e5533d;
}

.send {
  border: none;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  font-size: 13.5px;
  font-weight: 600;
  padding: 8px 22px;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 3px 8px rgba(26, 115, 232, 0.3);
}

.send:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
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
  .ptitle {
    font-size: 17px;
  }
}
</style>
