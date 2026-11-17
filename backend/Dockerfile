FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system --gid 10001 cybersentinel \
    && useradd --system --uid 10001 --gid cybersentinel --no-create-home cybersentinel

COPY pyproject.toml constraints.txt ./
COPY src ./src

RUN python -m pip install --no-cache-dir --constraint constraints.txt .

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "cybersentinel_backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
