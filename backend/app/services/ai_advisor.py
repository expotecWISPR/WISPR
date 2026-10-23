"""
IA de WISPR (Together AI · Llama 3.3 70B): escribe la HISTORIA de cada reto.

Cambio del 13 oct (guía del ingeniero, fase 5). Antes se le pedía a la IA el
reto entero (narrativa + flag + técnica + dificultad) y, con solo dos
técnicas posibles, lo único que podía variar era el texto: terminaba
repitiendo los ejemplos. Ahora el reparto es:

  * El BACKEND decide la técnica, la dificultad (motor adaptativo,
    difficulty.py) y la flag (`secrets`, challenge_generator.generate_flag).
    Esos valores son los que hacen distinto al reto de verdad.
  * La IA recibe todo eso ya decidido, más un escenario elegido al azar y
    los títulos que el jugador ya vio, y devuelve SOLO `title`,
    `description` y `hint`.

Lo que devuelve la IA es texto no confiable: se valida con
`ChallengeNarrative` (largos, sin llaves ni nada que parezca una flag, sin
repetir títulos) y después todo el reto pasa por `ChallengeSpec` antes de
generar el archivo (challenge_factory.py). Si la IA falla, tarda, no hay API
key, se pasó del límite por jugador o devuelve algo inválido, se usa una
historia de plantilla: el jugador nunca ve un error por culpa de la IA.
"""

from __future__ import annotations

import json
import logging
import random
import re
import ssl
from typing import Any, Iterable

import httpx
import truststore
from pydantic import BaseModel, Field, ValidationError, field_validator
from together import Together

from app.core import rate_limit
from app.core.config import settings
from app.services.technique_info import TECHNIQUES, technique_level

log = logging.getLogger(__name__)

# Modelo base, vía inferencia estándar de Together AI (sin fine-tuning
# todavía). Cuando el LoRA esté listo, se cambia SOLO este valor.
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

# Si la IA tarda más que esto, el reto se crea con la plantilla: el jugador
# está esperando la respuesta de su envío de flag.
TIMEOUT_SECONDS = 12
# Presupuesto del proyecto ($300-400 USD en total): cada jugador puede
# disparar como mucho estas llamadas por hora; después, plantillas.
CALLS_PER_PLAYER_PER_HOUR = 20

# Escenarios fijos: se elige uno al azar en cada reto para que la IA no caiga
# siempre en "una empresa". (nombre corto, frase para el prompt)
THEMES = [
    ("Cafetería", "la cafetería del colegio"),
    ("Hospital", "un hospital regional"),
    ("Colegio", "la oficina administrativa de un colegio"),
    ("Fábrica", "una fábrica de alimentos"),
    ("Estadio", "un estadio durante un partido de fútbol"),
    ("Biblioteca", "la biblioteca municipal"),
    ("Aeropuerto", "la sala de espera de un aeropuerto"),
    ("Banco", "la sucursal de un banco"),
    ("Hotel", "el lobby de un hotel de playa"),
    ("Laboratorio", "un laboratorio de investigación universitario"),
    ("Concierto", "un concierto al aire libre"),
    ("Farmacia", "una farmacia de barrio"),
    ("Feria", "una feria científica estudiantil"),
    ("Taller", "un taller mecánico"),
    ("Museo", "un museo de historia natural"),
]

# Escenario escrito por el usuario al pedir un reto (13 oct): letras, números y
# espacios, corto. Va al prompt como dato; aunque alguien intente "darle
# órdenes" a la IA por acá, lo único que puede cambiar es el texto de la
# historia, que igual se valida (ChallengeNarrative) y que solo ve quien lo pidió
# o los estudiantes de un profesor. Nunca toca la flag, la técnica ni el archivo.
CUSTOM_THEME = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]{3,40}$")


def resolve_theme(value: str | None) -> tuple[str, str] | None:
    """
    Escenario pedido por el usuario -> (nombre corto, frase para el prompt).
    None = al azar. Lanza ValueError si el texto no es aceptable.
    """
    value = " ".join(str(value or "").split())
    if not value:
        return None
    for short, long in THEMES:
        if value.casefold() == short.casefold():
            return short, long
    if not CUSTOM_THEME.match(value):
        raise ValueError("El escenario debe tener de 3 a 40 letras, números o espacios.")
    return value[:1].upper() + value[1:], value


# Plantillas de respaldo (sin IA). Igual varían con el escenario.
_FALLBACK = {
    "xor_singlebyte": {
        "title": "Archivo cifrado en {short}",
        "description": (
            "En {long} alguien dejó un archivo cifrado en una memoria USB olvidada. El responsable de "
            "sistemas sospecha que se usó un XOR casero. Analiza el archivo y recupera el mensaje oculto."
        ),
        "hint": "Los cifrados XOR caseros tienen un punto débil: sabes cómo empieza el mensaje.",
    },
    "iv_reuse_wep": {
        "title": "Red WEP en {short}",
        "description": (
            "La red inalámbrica de {long} todavía usa WEP. Un técnico capturó tráfico y sospecha que el "
            "router repite vectores de inicialización. Analiza la captura y recupera el mensaje cifrado."
        ),
        "hint": "Cuando dos tramas WEP comparten IV, también comparten keystream.",
    },
    "caesar_vigenere": {
        "title": "Mensaje antiguo en {short}",
        "description": (
            "En {long} apareció una nota con letras que no forman palabras. Parece cifrada con un método "
            "clásico, de los que se usaban hace siglos. Analiza el archivo y recupera el mensaje original."
        ),
        "hint": "Los cifrados clásicos solo mueven letras: los números y símbolos te dicen dónde está cada parte.",
    },
    "encoding_layers": {
        "title": "Texto envuelto en {short}",
        "description": (
            "En {long} se encontró un archivo de texto con una cadena extraña. No parece cifrada, sino "
            "codificada una o varias veces. Identifica cada capa y recupera el mensaje que esconde."
        ),
        "hint": "Codificar no es cifrar: fíjate en qué caracteres usa la cadena para saber cómo se codificó.",
    },
    "http_plaintext_pcap": {
        "title": "Tráfico sin candado en {short}",
        "description": (
            "El equipo de redes de {long} capturó tráfico de la intranet. Sospechan que un formulario envía "
            "información sin cifrar. Analiza la captura y recupera el mensaje que viajó a la vista."
        ),
        "hint": "Si una página no usa HTTPS, todo lo que envía se puede leer en la captura.",
    },
    "stego_png": {
        "title": "La foto de {short}",
        "description": (
            "Desde {long} alguien compartió una imagen que parece normal, pero pesa más de lo esperado. "
            "Sospechan que oculta un mensaje. Analiza la imagen y recupéralo."
        ),
        "hint": "Una imagen guarda más que píxeles: revisa sus metadatos y lo que hay alrededor del contenido visible.",
    },
}

_SYSTEM_PROMPT = (
    "Eres el narrador de WISPR, una plataforma CTF educativa para estudiantes de colegio en Costa Rica. "
    "Escribes SOLO la historia de un reto cuya parte técnica ya está decidida y construida por el equipo. "
    "Responde únicamente con un objeto JSON válido, sin texto antes o después y sin bloques de markdown, "
    "con exactamente estas llaves:\n"
    '  "title": título original y corto (máximo 50 caracteres), sin la palabra "reto"\n'
    '  "description": de 2 a 4 oraciones (máximo 500 caracteres), hablándole al estudiante de "tú", que lo '
    "sitúe en el escenario indicado y diga qué archivo recibió y qué debe recuperar\n"
    '  "hint": una sola oración que oriente sin dar la solución, coherente con el resumen técnico\n'
    "Reglas: no escribas flags, prefijos de flags ni ningún carácter de llave; no inventes herramientas, archivos ni pasos "
    "distintos a los del resumen técnico; no menciones la dificultad ni los puntos; no uses nombres de "
    "personas o empresas reales; escribe en español."
)

# Llaves = formato de flag (WISPR{...}). La palabra "flag" sí se permite: es
# natural que la historia diga "recupera la flag".
_FORBIDDEN = re.compile(r"[{}]")


class ChallengeNarrative(BaseModel):
    """Lo único que la IA puede aportar a un reto. Cualquier otra llave se ignora."""

    title: str = Field(..., min_length=4, max_length=60)
    description: str = Field(..., min_length=40, max_length=700)
    hint: str = Field(..., min_length=10, max_length=300)

    @field_validator("title", "description", "hint", mode="before")
    @classmethod
    def _limpiar(cls, value: Any) -> Any:
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("title", "description", "hint")
    @classmethod
    def _sin_flags(cls, value: str) -> str:
        # La flag la genera el backend y nunca se le pasa a la IA; igual se
        # rechaza cualquier cosa que parezca una, para que el texto no pueda
        # confundir al jugador ni "filtrar" un formato de respuesta.
        if _FORBIDDEN.search(value):
            raise ValueError("El texto no puede contener llaves (formato de flag).")
        return value


class AIUnavailable(Exception):
    """La IA no respondió algo usable. Siempre se resuelve con la plantilla."""


def _client() -> Together:
    # truststore: Python usa los certificados del sistema operativo (como el
    # navegador). Hace falta en PCs con antivirus que inspecciona HTTPS (ej.
    # Norton): sin esto, la llamada falla con CERTIFICATE_VERIFY_FAILED.
    http_client = httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=TIMEOUT_SECONDS)
    return Together(api_key=settings.TOGETHER_API_KEY, timeout=TIMEOUT_SECONDS, max_retries=0, http_client=http_client)


def _build_messages(technique: str, difficulty: str, theme: str, avoid_titles: Iterable[str]) -> list[dict[str, str]]:
    level = technique_level(technique, difficulty)
    avoid = [t for t in avoid_titles if t][:15]
    # Probado contra la API real (13 oct): si el resumen dice "WISPR{", la IA
    # lo copia en la historia y ChallengeNarrative la rechaza por las llaves.
    # Se le pasa descrito en palabras; el objetivo técnico real (con el
    # prefijo) lo ve el jugador igual, porque sale de technique_info.py.
    summary = level["objective"].replace("WISPR{", "el prefijo conocido de la flag")
    user_prompt = (
        f"Técnica: {TECHNIQUES[technique]['name']}.\n"
        f"Archivo que recibe el estudiante: {level['file_desc']} (.{level['ext']}).\n"
        "Lo que el estudiante debe recuperar: la flag, un texto secreto escondido en ese archivo.\n"
        f"Resumen técnico (es verdad; no lo contradigas): {summary}\n"
        f"Escenario obligatorio: {theme}.\n"
        + (f"No repitas ninguno de estos títulos: {json.dumps(avoid, ensure_ascii=False)}." if avoid else "")
    )
    return [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]


def _extract_json(raw_text: str) -> dict[str, Any]:
    """
    Extrae el primer objeto JSON del texto que devuelve el modelo. Los LLM a
    veces lo envuelven en ```json ... ``` aunque se les pida que no; esto lo
    tolera. Si no hay JSON válido, propaga json.JSONDecodeError.
    """
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def request_narrative(technique: str, difficulty: str, theme: str, avoid_titles: Iterable[str] = ()) -> ChallengeNarrative:
    """Una llamada a Together AI, validada. Lanza AIUnavailable si algo sale mal."""
    avoid_titles = list(avoid_titles)
    try:
        response = _client().chat.completions.create(
            model=MODEL_NAME,
            messages=_build_messages(technique, difficulty, theme, avoid_titles),
            temperature=0.9,  # alta a propósito: queremos variedad de historias
            max_tokens=400,
        )
        narrative = ChallengeNarrative(**_extract_json(response.choices[0].message.content or ""))
    except (ValidationError, json.JSONDecodeError, TypeError) as exc:
        raise AIUnavailable(f"respuesta inválida de la IA: {exc.__class__.__name__}") from exc
    except Exception as exc:  # red, timeout, API key inválida, cuota...
        raise AIUnavailable(f"la IA no respondió: {exc.__class__.__name__}") from exc
    if narrative.title.casefold() in {t.casefold() for t in avoid_titles}:
        raise AIUnavailable("la IA repitió un título que el jugador ya vio")
    return narrative


def fallback_narrative(technique: str, theme_short: str, theme_long: str) -> ChallengeNarrative:
    template = _FALLBACK[technique]
    return ChallengeNarrative(
        title=template["title"].format(short=theme_short),
        description=template["description"].format(long=theme_long),
        hint=template["hint"],
    )


def generate_narrative(
    technique: str,
    difficulty: str,
    avoid_titles: Iterable[str] = (),
    player_key: str | None = None,
    theme: tuple[str, str] | None = None,
) -> tuple[ChallengeNarrative, str, str]:
    """
    Historia para un reto nuevo. `theme` = escenario elegido por el usuario
    (ver resolve_theme); sin él, uno al azar que no haya visto. Nunca lanza:
    devuelve (narrativa, origen "ai" | "template", motivo si se usó la plantilla).
    """
    avoid_titles = list(avoid_titles)
    if theme is None:
        seen = " ".join(t.casefold() for t in avoid_titles)
        theme = random.choice([t for t in THEMES if t[0].casefold() not in seen] or THEMES)
    theme_short, theme_long = theme
    try:
        if not (settings.TOGETHER_API_KEY or "").strip():
            raise AIUnavailable("no hay TOGETHER_API_KEY")
        if player_key is not None:
            try:
                rate_limit.check("ai", player_key, CALLS_PER_PLAYER_PER_HOUR, 3600)
            except rate_limit.RateLimitExceeded as exc:
                raise AIUnavailable("límite de llamadas a la IA por hora") from exc
        return request_narrative(technique, difficulty, theme_long, avoid_titles), "ai", ""
    except AIUnavailable as exc:
        log.warning("IA no disponible, se usa la plantilla: %s", exc)
        return fallback_narrative(technique, theme_short, theme_long), "template", str(exc)
