# coc-star API

Python API service for rooms, board state, chat, dice commands and future AI capabilities.

## Local development

```powershell
uv sync --dev
uv run uvicorn coc_star_api.main:app --reload --app-dir src
```

Health check: `http://127.0.0.1:8000/health`

