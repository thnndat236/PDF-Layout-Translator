FROM python:3.10-slim


RUN apt-get update && apt-get install -y \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*


ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    VIRTUAL_ENV="/app/.venv"


WORKDIR /app


COPY uv.lock pyproject.toml ./


RUN pip install --no-cache-dir uv
RUN uv sync --locked


RUN uvicorn --version


COPY ./app .


EXPOSE 30000


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "30000"]
