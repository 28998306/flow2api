from fastapi import APIRouter

from app.api.routes import admin, auth, generation, openai, users, ws

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(generation.router)
api_router.include_router(admin.router)

# WebSocket router is mounted without the /api/v1 prefix in main.py
ws_router = ws.router
openai_router = openai.router
