"""
Especificación de un reto generado por IA (ChallengeSpec).

Este es el punto de control de todo el pipeline de generación de retos
(ver docs/pipeline_ia_retos.md). Together AI devuelve texto — no confiable
por sí mismo — y este schema es lo único que decide si ese texto se
convierte en un objeto Python seguro de usar.

Regla de oro: si el JSON de la IA no pasa esta validación, el flujo se
detiene aquí. Nunca debe llegar un JSON inválido a challenge_generator.py.
En particular, el campo `technique` es un Literal con el registro fijo de
técnicas ya construidas por el equipo — la IA elige de esa lista, nunca
puede inventar una técnica nueva ni hacer que el backend ejecute algo
fuera de ese registro.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Formato esperado de toda flag de la plataforma: FLAG{contenido}.
# Se valida acá (y no solo "a ojo" en el prompt) porque la IA genera texto,
# no garantías — este regex es la última línea de defensa antes de guardar
# la flag en Supabase.
FLAG_PATTERN = re.compile(r"^FLAG\{[^{}]+\}$")


class ChallengeSpec(BaseModel):
    """
    Especificación de un reto, tal como la genera el modelo de IA
    (Llama 3.3 70B + LoRA vía Together AI) antes de materializarse.

    Ejemplo (ver docs/pipeline_ia_retos.md):
        {
          "id": "crypto-wifi-01",
          "difficulty": "easy",
          "category": "network",
          "description": "Red WEP antigua con reutilización de IVs capturada.",
          "technique": "iv_reuse_wep",
          "flag": "FLAG{wep_died_for_a_reason}",
          "hint": "Busca IVs repetidos en el pcap.",
          "solution": "Extraer IVs duplicados, recuperar keystream, XOR..."
        }
    """

    id: str = Field(..., min_length=1, description="Identificador único del reto, ej. 'crypto-wifi-01'.")

    difficulty: Literal["easy", "medium", "hard"]

    category: Literal["web", "crypto", "forensics", "network", "osint"]

    description: str = Field(
        ..., min_length=1, description="Narrativa del reto que ve el estudiante."
    )

    # Registro fijo de técnicas que el equipo ya programó y probó en
    # challenge_generator.py. Si la IA devuelve cualquier otro valor,
    # Pydantic rechaza el objeto antes de intentar generar nada.
    technique: Literal["iv_reuse_wep", "xor_singlebyte"]

    flag: str = Field(..., description="Flag exacta que debe coincidir al validar la respuesta del estudiante.")

    hint: str = Field(..., min_length=1, description="Pista visible para el estudiante.")

    solution: str = Field(
        ..., min_length=1, description="Explicación de la solución, para material de apoyo/docente."
    )

    @field_validator("flag")
    @classmethod
    def flag_debe_tener_formato_valido(cls, value: str) -> str:
        if not FLAG_PATTERN.match(value):
            raise ValueError(
                f"La flag '{value}' no tiene el formato esperado FLAG{{...}}."
            )
        return value
