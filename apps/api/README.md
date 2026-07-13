# coc-star API

Python API service for rooms, board state, chat, dice commands and future AI capabilities.

## Local development

```powershell
uv sync --dev
uv run uvicorn coc_star_api.main:app --reload --app-dir src
```

Health check: `http://127.0.0.1:8000/health`

Account endpoints:

- `POST /api/auth/register` with `{ "username": "你的账号", "password": "至少 8 位" }`
- `POST /api/auth/login` with the same body
- `POST /api/auth/refresh` with `{ "refresh_token": "..." }`

Create a room with `POST /api/rooms` and `{ "display_name": "你的名字" }`.
Join an existing room with `POST /api/rooms/{room_id}/join` and the same body.
Both endpoints return a signed `access_token` for the room WebSocket.

The API uses SQLite by default for local development. Set `DATABASE_URL` to an
`postgresql+asyncpg://...` URL in production. Board tokens are restored from
the database when a room is first opened.
