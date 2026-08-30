FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖(PDF 解析需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite 数据目录
RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:////app/data/interview.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
