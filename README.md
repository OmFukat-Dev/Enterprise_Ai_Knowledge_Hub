# Enterprise AI Knowledge Hub (Free and Open-Source Stack)

RAG application with:
- FastAPI backend
- Streamlit frontend
- Local embeddings + reranking (`sentence-transformers`)
- Open-source vector storage (`Qdrant` local mode)
- Local LLM inference (`Ollama`)

No paid API keys are required.

## Architecture

- `app.py`: FastAPI API (`/api/upload`, `/api/ask`, `/health`)
- `frontend/dashboard.py`: Streamlit UI
- `src/ingestion/*`: PDF extraction and chunking
- `src/retrieval/vector_store.py`: Qdrant local + in-memory fallback
- `src/generation/llm_integration.py`: local Ollama generation
- `src/core/*`, `src/models/*`, `src/api/routers/*`: auth/data layer

## Quick Start (Windows)

1. Create env file:
```powershell
Copy-Item .env.example .env
```

2. Create and activate venv:
```powershell
python -m venv venv
.\venv\Scripts\activate
```

3. Install dependencies:
```powershell
pip install -r requirements.txt
```

4. Install Ollama and pull model:
```powershell
ollama pull llama3
```

5. Run frontend-only mode (default in `run.bat`):
```powershell
.\run.bat
```

6. Run backend API separately (optional):
```powershell
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

- `GET /health`
- `POST /api/upload` (multipart form with `file=.pdf`)
- `POST /api/ask` (form field `question`)
- Swagger: `http://127.0.0.1:8000/api/docs`

## Database and Migrations

Default DB is SQLite:
- `DATABASE_URL=sqlite+aiosqlite:///./enterprise_ai_hub.db`

Run migrations:
```powershell
alembic upgrade head
```

## Free Deployment Options

- Backend: Fly.io free allowance / Railway hobby free windows vary / self-hosted VPS
- Frontend: Streamlit Community Cloud (for UI-only patterns) or self-hosted
- Recommended for full free + no billing lock-in: self-hosted on local machine, mini PC, or free community compute where available

## Security Notes

- Do not commit real secrets in `.env`
- Rotate `SECRET_KEY` and `JWT_SECRET_KEY` before any public deployment
- Keep CORS restricted in production

