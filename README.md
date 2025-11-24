# PDF-Layout-Translator

## Backend - FastAPI, Redis, Celery, Flower

```shell
# Navigate to backend
cd backend
source .venv/bin/activate

# Docker compose up
docker build -t {username}/pdf-layout-translator:latest .
docker compose -f docker-compose.yaml up

# Health check container
docker ps
```

Access `flower` at: http://localhost:5555

## Frontend - Gradio

```shell
# Navigate to frontend
cd frontend
source .venv/bin/activate

# Run gradio ui
python main.py
```