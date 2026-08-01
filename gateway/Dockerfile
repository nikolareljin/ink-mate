FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system inkmate && adduser --system --ingroup inkmate inkmate
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER inkmate
EXPOSE 8080
CMD ["uvicorn", "inkmate_gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
