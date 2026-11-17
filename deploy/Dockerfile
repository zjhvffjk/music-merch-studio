FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY deploy/requirements.txt /app/deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt \
    && playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
COPY . /app
RUN useradd --uid 10001 --create-home studio && mkdir -p /app/outputs /app/logs \
    && chown -R studio:studio /app/outputs /app/logs /opt/browsers
USER studio
EXPOSE 8080
CMD ["python", "-m", "deploy.start"]
