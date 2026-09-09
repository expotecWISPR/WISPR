"""
Router principal de la versión 1 de la API.

Junta todos los routers de app/api/v1/endpoints/ en uno solo, para que
main.py solo tenga que incluir este archivo en vez de cada endpoint por
separado. Cuando se agregue un endpoint nuevo (challenges, flags,
scoreboard), se importa y se agrega acá con include_router().
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
