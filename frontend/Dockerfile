FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]
