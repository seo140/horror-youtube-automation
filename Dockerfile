FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates fonts-noto-core fonts-noto-extra && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/.cache/voice && \
 curl -fLsS --retry 3 --output /app/.cache/voice/ar_JO-kareem-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx" && \
 curl -fLsS --retry 3 --output /app/.cache/voice/ar_JO-kareem-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json" && \
 test "$(wc -c < /app/.cache/voice/ar_JO-kareem-medium.onnx)" -gt 1000000
CMD uvicorn server:app --host 0.0.0.0 --port "${PORT:-10000}" --workers 1
