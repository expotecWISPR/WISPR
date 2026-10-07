"""
Router principal de la versión 1 de la API.

Junta todos los routers de app/api/v1/endpoints/ en uno solo, para que
main.py solo tenga que incluir este archivo en vez de cada endpoint por
separado. Cuando se agregue un endpoint nuevo (challenges, flags,
scoreboard), se importa y se agrega acá con include_router().

`auth.py` y `users.py` (login simple sin MFA, JWT stateless) se dieron de
baja el 7 oct al migrar el auth real a `app/api/players.py`, montado por
separado en `/api/players` — ver ese archivo y el checkpoint en CLAUDE.md.
"""

from fastapi import APIRouter

api_router = APIRouter()
