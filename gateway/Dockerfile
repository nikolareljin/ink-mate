FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/var/cache/inkmate/huggingface \
    XDG_CACHE_HOME=/var/cache/inkmate

RUN addgroup --system inkmate && adduser --system --ingroup inkmate inkmate \
    && install -d -o inkmate -g inkmate /var/cache/inkmate
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[audio]"

USER inkmate
EXPOSE 8080
EXPOSE 37653/udp
CMD ["sh", "-c", "uvicorn inkmate_gateway.app:app --host ${INKMATE_BIND_ADDRESS:-0.0.0.0} --port ${INKMATE_GATEWAY_PORT:-8080}"]
