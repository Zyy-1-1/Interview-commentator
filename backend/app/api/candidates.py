"""候选人接口:上传简历并触发解析 + 简历×岗位匹配分析。"""
import json
import logging
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..agents.matcher import match_resume_to_job
from ..agents.resume_parser import parse_resume_file
from ..config import settings
from ..db import get_db
from ..models import Candidate, Job
from ..schemas import CandidateCreated, CandidateOut
from ..security import (
    CANDIDATE_HEADER,
    REVIEW_HEADER,
    issue_candidate_token,
    require_admin,
    verify_candidate_access,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/candidates", tags=["candidates"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
CHUNK_SIZE = 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def _save_upload(file: UploadFile) -> Path:
    """分块保存并校验真实文件类型；调用方负责最终删除临时文件。"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"不支持的文件类型 {suffix or '(无后缀)'},支持 PDF/DOCX/TXT/MD")
    # 随机文件名,避免路径穿越/重名
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = UPLOAD_DIR / safe_name
    size = 0
    try:
        file.file.seek(0)
        with path.open("wb") as target:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        413,
                        f"文件过大,上限为 {settings.max_upload_bytes // (1024 * 1024)} MB",
                    )
                target.write(chunk)
        if size == 0:
            raise HTTPException(400, "上传文件为空")
        _validate_file_signature(path, suffix)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _validate_file_signature(path: Path, suffix: str) -> None:
    """后缀之外再检查文件头/容器结构，拒绝伪装文件与 DOCX 压缩炸弹。"""
    if suffix == ".pdf":
        with path.open("rb") as source:
            header = source.read(5)
        if header != b"%PDF-":
            raise HTTPException(400, "文件内容不是有效 PDF")
        return
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                total_size = sum(info.file_size for info in archive.infolist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise HTTPException(400, "文件内容不是有效 DOCX")
                if total_size > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise HTTPException(413, "DOCX 解压后内容过大")
        except zipfile.BadZipFile as e:
            raise HTTPException(400, "文件内容不是有效 DOCX") from e
        return
    with path.open("rb") as source:
        sample = source.read(64 * 1024)
    if b"\x00" in sample:
        raise HTTPException(400, "文本文件包含二进制内容")


@router.get("", response_model=list[CandidateOut])
def list_candidates(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    return db.query(Candidate).order_by(Candidate.created_at.desc()).all()


@router.post("", response_model=CandidateCreated)
async def upload_candidate(file: UploadFile, db: Session = Depends(get_db)):
    path: Path | None = None
    try:
        # 文件 I/O、PDF/DOCX 解析和同步 LLM SDK 都移到线程池，避免阻塞事件循环。
        path = await run_in_threadpool(_save_upload, file)
        parsed = await run_in_threadpool(parse_resume_file, path)
        if not isinstance(parsed, dict):
            raise ValueError("解析结果格式错误")
    except Exception as e:  # noqa: BLE001
        if isinstance(e, HTTPException):
            raise
        logger.warning("简历解析失败 %s: %s", path.name, e)
        raise HTTPException(422, "简历解析失败,请检查文件是否可正常打开后重试") from e
    finally:
        if path is not None:
            path.unlink(missing_ok=True)
        await file.close()

    text = parsed.pop("_source_text", None)
    access_token, access_token_hash = issue_candidate_token()
    cand = Candidate(
        name=parsed.get("basic", {}).get("name"),
        resume_path=None,
        resume_text=(text[: settings.max_resume_text_chars] if isinstance(text, str) else None),
        parsed_resume=json.dumps(parsed, ensure_ascii=False),
        access_token_hash=access_token_hash,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return CandidateCreated(
        id=cand.id,
        name=cand.name,
        parsed_resume=cand.parsed_resume,
        created_at=cand.created_at,
        access_token=access_token,
    )


@router.get("/{candidate_id}/match/{job_id}")
def match_to_job(
    candidate_id: int,
    job_id: int,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    """面试前的人岗匹配分析(简历 × 岗位维度)。"""
    cand = db.get(Candidate, candidate_id)
    job = db.get(Job, job_id)
    if not cand:
        raise HTTPException(404, "候选人不存在")
    verify_candidate_access(
        cand.access_token_hash,
        candidate_token,
        admin_passphrase,
    )
    if not job:
        raise HTTPException(404, "岗位不存在")
    if job.status != "approved":
        raise HTTPException(404, "岗位不存在或未上架")
    dims = json.loads(job.dimensions or "[]")
    if not dims:
        raise HTTPException(422, "该岗位尚未完成 JD 分析,无法匹配")
    parsed = json.loads(cand.parsed_resume) if cand.parsed_resume else None
    try:
        result = match_resume_to_job(
            parsed_resume=parsed,
            resume_text=cand.resume_text,
            job_title=job.title,
            jd_text=job.jd_text,
            dimensions=dims,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(
            "人岗匹配失败(candidate=%s, job=%s): %s",
            candidate_id,
            job_id,
            e,
        )
        raise HTTPException(502, "匹配分析失败,请稍后重试") from e
    return result


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "候选人不存在")
    return cand
