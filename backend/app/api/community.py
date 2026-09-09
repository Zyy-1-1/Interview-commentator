"""交流区接口(任务5:牛客式板块 MVP — 发帖 / 评论 / 点赞)。

匿名身份:浏览器本地随机生成令牌(X-Community-Token 请求头),
服务端只保存其 SHA-256;昵称由哈希前 4 位派生(如「面评家用户_3f8a」),
同一令牌在整个会话内的发言/点赞身份稳定一致。

- GET  /api/community/me                     查看当前匿名昵称
- GET  /api/community/posts                  帖子列表(最新在前)
- POST /api/community/posts                  发帖
- GET  /api/community/posts/{id}             帖子详情(含评论)
- POST /api/community/posts/{id}/comments    评论
- POST /api/community/posts/{id}/like        点赞/取消(幂等 toggle)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Comment, Post, PostLike
from ..schemas import (
    CommentCreate,
    CommentOut,
    LikeOut,
    PostCreate,
    PostDetailOut,
    PostOut,
)
from ..security import COMMUNITY_HEADER, hash_candidate_token

router = APIRouter(prefix="/api/community", tags=["community"])

NICK_PREFIX = "面评家用户_"
MIN_TOKEN_LEN = 16


def _nickname(token_hash: str) -> str:
    return f"{NICK_PREFIX}{token_hash[:4]}"


def _viewer_hash(token: str | None) -> str | None:
    """可选身份:读请求不带令牌时视为游客(可看不可发)。"""
    if not token or len(token) < MIN_TOKEN_LEN:
        return None
    return hash_candidate_token(token)


def require_identity(
    token: Annotated[str | None, Header(alias=COMMUNITY_HEADER)] = None,
) -> tuple[str, str]:
    """写操作(发帖/评论/点赞)必须携带合法匿名令牌,返回 (昵称, 哈希)。"""
    h = _viewer_hash(token)
    if h is None:
        raise HTTPException(401, "缺少社区身份凭证,请刷新页面后重试")
    return _nickname(h), h


def _post_out(
    db: Session,
    post: Post,
    viewer_hash: str | None,
    comment_count: int | None = None,
    liked: bool | None = None,
) -> PostOut:
    if comment_count is None:
        comment_count = (
            db.query(func.count(Comment.id))
            .filter(Comment.post_id == post.id)
            .scalar()
        ) or 0
    if liked is None and viewer_hash:
        liked = (
            db.query(PostLike.id)
            .filter(PostLike.post_id == post.id, PostLike.token_hash == viewer_hash)
            .first()
            is not None
        )
    return PostOut(
        id=post.id,
        title=post.title,
        content=post.content,
        author_name=post.author_name,
        likes_count=post.likes_count,
        comment_count=comment_count,
        liked_by_me=bool(liked),
        created_at=post.created_at,
    )


@router.get("/me")
def whoami(name_hash: tuple[str, str] = Depends(require_identity)):
    name, _ = name_hash
    return {"nickname": name}


@router.get("/posts", response_model=list[PostOut])
def list_posts(
    limit: int = 50,
    db: Session = Depends(get_db),
    viewer: Annotated[str | None, Header(alias=COMMUNITY_HEADER)] = None,
):
    viewer_hash = _viewer_hash(viewer)
    posts = (
        db.query(Post)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    if not posts:
        return []
    # 评论数与「我赞过」各用一条聚合查询,避免逐帖 N+1
    counts = dict(
        db.query(Comment.post_id, func.count(Comment.id))
        .filter(Comment.post_id.in_([p.id for p in posts]))
        .group_by(Comment.post_id)
        .all()
    )
    liked_ids = set()
    if viewer_hash:
        liked_ids = {
            pid
            for (pid,) in db.query(PostLike.post_id).filter(
                PostLike.post_id.in_([p.id for p in posts]),
                PostLike.token_hash == viewer_hash,
            ).all()
        }
    return [
        _post_out(db, p, viewer_hash, counts.get(p.id, 0), p.id in liked_ids)
        for p in posts
    ]


@router.post("/posts", response_model=PostOut)
def create_post(
    body: PostCreate,
    db: Session = Depends(get_db),
    identity: tuple[str, str] = Depends(require_identity),
):
    name, token_hash = identity
    post = Post(
        title=body.title,
        content=body.content,
        author_name=name,
        author_token_hash=token_hash,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _post_out(db, post, token_hash, comment_count=0, liked=False)


def _get_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "帖子不存在")
    return post


@router.get("/posts/{post_id}", response_model=PostDetailOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    viewer: Annotated[str | None, Header(alias=COMMUNITY_HEADER)] = None,
):
    post = _get_post(db, post_id)
    viewer_hash = _viewer_hash(viewer)
    comments = (
        db.query(Comment).filter(Comment.post_id == post.id).order_by(Comment.id).all()
    )
    base = _post_out(db, post, viewer_hash, comment_count=len(comments))
    return PostDetailOut(**base.model_dump(), comments=comments)


@router.post("/posts/{post_id}/comments", response_model=CommentOut)
def add_comment(
    post_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    identity: tuple[str, str] = Depends(require_identity),
):
    _get_post(db, post_id)
    name, token_hash = identity
    comment = Comment(
        post_id=post_id,
        content=body.content,
        author_name=name,
        author_token_hash=token_hash,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.post("/posts/{post_id}/like", response_model=LikeOut)
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    identity: tuple[str, str] = Depends(require_identity),
):
    post = _get_post(db, post_id)
    _, token_hash = identity
    existing = (
        db.query(PostLike)
        .filter(PostLike.post_id == post.id, PostLike.token_hash == token_hash)
        .first()
    )
    if existing:
        db.delete(existing)
        post.likes_count = max(0, (post.likes_count or 0) - 1)
        liked = False
    else:
        db.add(PostLike(post_id=post.id, token_hash=token_hash))
        post.likes_count = (post.likes_count or 0) + 1
        liked = True
    db.commit()
    return LikeOut(liked=liked, likes_count=post.likes_count)
