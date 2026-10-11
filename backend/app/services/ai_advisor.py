"""
Cliente de Together AI para generar la especificación de un reto.

Esta es la primera mitad del pipeline de generación de retos con IA (ver
docs/pipeline_ia_retos.md): le pide al modelo un JSON con narrativa, flag,
técnica y dificultad, y devuelve ese JSON ya parseado a dict.

Importante — este módulo NO valida el resultado. Devuelve texto de un LLM
convertido a dict, nada más. La validación real (¿están todos los campos?
¿tiene los tipos correctos? ¿la `technique` existe en el registro fijo?
¿la flag tiene el formato correcto?) la hace ChallengeSpec
(app/schemas/challenge.py) cuando quien llama a esta función construye el
objeto con `ChallengeSpec(**resultado)`.

Por qué separar "pedirle a la IA" de "validar lo que respondió": un LLM
puede devolver JSON mal formado, con un campo faltante, o eligiendo una
`technique` que no existe en el registro del equipo. Ninguno de esos casos
debe ejecutar código — deben fallar acá (error claro) o en la validación
de Pydantic más adelante, nunca de forma silenciosa.
"""

import json
import re
from typing import Any, get_args

from together import Together

from app.core.config import settings
from app.schemas.challenge import ChallengeSpec

# Modelo base, vía inferencia estándar de Together AI (sin fine-tuning
# todavía). Cuando el fine-tuning con LoRA esté listo, el plan es cambiar
# SOLO este valor por el nombre del modelo ajustado — el resto del
# pipeline (prompt, parsing, validación) no cambia. Ver "Próximos pasos de
# implementación" en docs/pipeline_ia_retos.md.
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

# Se leen las listas válidas directamente desde ChallengeSpec en vez de
# repetirlas acá a mano — así el prompt nunca queda desincronizado del
# registro real de técnicas/categorías/dificultades que Pydantic valida.
_TECHNIQUES = get_args(ChallengeSpec.model_fields["technique"].annotation)
_CATEGORIES = get_args(ChallengeSpec.model_fields["category"].annotation)
_DIFFICULTIES = get_args(ChallengeSpec.model_fields["difficulty"].annotation)

_SYSTEM_PROMPT = (
    "Sos un generador de especificaciones de retos de ciberseguridad para una "
    "plataforma CTF educativa de estudiantes de colegio. Respondé "
    "ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes o "
    "después, y sin bloques de markdown (nada de ```), con exactamente "
    "estos campos:\n"
    '  "id": string único, en minúsculas y con guiones (ej. "network-wep-03")\n'
    f'  "difficulty": obligatoriamente uno de {list(_DIFFICULTIES)}\n'
    f'  "category": obligatoriamente uno de {list(_CATEGORIES)}\n'
    '  "description": narrativa del reto que va a leer el estudiante\n'
    f'  "technique": OBLIGATORIAMENTE uno de {list(_TECHNIQUES)} — nunca '
    "inventes un valor fuera de esta lista, aunque se te ocurra una técnica "
    "más interesante o más avanzada\n"
    '  "flag": string con formato exacto WISPR{contenido_en_snake_case}\n'
    '  "hint": pista visible para el estudiante si se traba\n'
    '  "solution": explicación de la solución, para material del docente\n'
)


def _build_messages(category: str, difficulty: str) -> list[dict[str, str]]:
    user_prompt = f"Generá un reto de categoría '{category}' con dificultad '{difficulty}'."
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _extract_json(raw_text: str) -> dict[str, Any]:
    """
    Extrae el primer objeto JSON del texto que devuelve el modelo.

    Los LLM a veces envuelven el JSON en un bloque ```json ... ``` aunque
    se les pida explícitamente no hacerlo — esto lo tolera sin necesidad
    de un parser más complejo. Si el texto no contiene JSON válido en
    ningún formato, deja que json.JSONDecodeError se propague: eso es una
    señal real de que hay que reintentar o usar el reto estático de
    respaldo (ver diagrama en docs/pipeline_ia_retos.md), no algo para
    silenciar acá.
    """
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def generate_challenge_spec_raw(category: str, difficulty: str) -> dict[str, Any]:
    """
    Le pide a Together AI la especificación de un reto y devuelve el JSON
    crudo como dict — SIN VALIDAR.

    Quien llama a esta función es responsable de pasarlo por
    ChallengeSpec(**resultado) antes de usarlo para generar cualquier
    archivo (ver app/services/challenge_generator.py). Esta función no
    hace esa validación a propósito: mezclar "pedirle algo a un LLM" con
    "decidir si el resultado es seguro de usar" sería juntar dos
    responsabilidades distintas en una función difícil de probar.
    """
    client = Together(api_key=settings.TOGETHER_API_KEY)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=_build_messages(category, difficulty),
        temperature=0.7,
        max_tokens=800,
    )
    raw_text = response.choices[0].message.content
    return _extract_json(raw_text)
