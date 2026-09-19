FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# rapidocr / PyMuPDF 等文档处理依赖的运行时库。
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN mkdir -p /app/data /app/uploads

EXPOSE 8000

# 抽取任务使用进程内队列，因此保持单 worker；不要增加 --workers。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
