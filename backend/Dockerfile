FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.19
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"
ENV ORDER_DB_PATH=/data/orders.sqlite3
ENV JOBFLOW_ANTHROPIC_MAX_CALLS=0
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
