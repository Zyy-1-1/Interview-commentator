FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app app ./app

# SQLite 持久目录 + 简历解析临时目录
RUN mkdir -p /app/data /app/uploads && chown app:app /app/data /app/uploads
ENV DATABASE_URL=sqlite:////app/data/interview.db
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
