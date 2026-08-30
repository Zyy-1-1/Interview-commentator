"""评估报告接口(W4 补齐完整报告页,当前仅返回已生成的报告)。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Interview

router = APIRouter(prefix="/api/interviews", tags=["reports"])


@router.get("/{interview_id}/report")
def get_report(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    if not interview.report:
        raise HTTPException(404, "报告尚未生成(面试未结束或评估未执行)")
    import json

    return {"interview_id": interview_id, "report": json.loads(interview.report)}
