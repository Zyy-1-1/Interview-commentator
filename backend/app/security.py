"""轻量后台鉴权依赖。

MVP 暂不引入账号系统；部署方通过 REVIEW_PASSPHRASE 配置审核口令，
后台请求统一放在 ``X-Review-Passphrase`` 请求头中。
"""
import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Header, HTTPException

from .config import settings

REVIEW_HEADER = "X-Review-Passphrase"
CANDIDATE_HEADER = "X-Candidate-Token"


def verify_review_passphrase(given: str | None) -> str:
    """校验后台口令并返回原值，便于作为 FastAPI 依赖复用。"""
    if not settings.review_passphrase:
        raise HTTPException(503, "服务端未配置 REVIEW_PASSPHRASE,后台功能不可用")
    if not hmac.compare_digest(given or "", settings.review_passphrase):
        raise HTTPException(401, "审核口令错误")
    return given or ""


def require_admin(
    passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
) -> str:
    return verify_review_passphrase(passphrase)


def issue_candidate_token() -> tuple[str, str]:
    """返回一次性明文令牌及其 SHA-256 哈希；数据库只保存后者。"""
    token = secrets.token_urlsafe(32)
    return token, hash_candidate_token(token)


def hash_candidate_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_candidate_access(
    expected_hash: str | None,
    candidate_token: str | None,
    admin_passphrase: str | None = None,
) -> None:
    """候选人令牌或后台口令任一通过即可读取候选人的私有资源。"""
    if expected_hash and candidate_token:
        actual_hash = hash_candidate_token(candidate_token)
        if hmac.compare_digest(actual_hash, expected_hash):
            return
    if admin_passphrase:
        verify_review_passphrase(admin_passphrase)
        return
    if expected_hash is None:
        raise HTTPException(401, "旧数据缺少访问凭证,请重新上传简历或使用后台口令")
    raise HTTPException(401, "候选人访问凭证无效或已丢失")
