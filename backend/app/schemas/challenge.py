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

# Formato esperado de toda flag de la plataforma: WISPR{contenido}.
# Mismo regex que el prototipo (`wispr_terminal_professional`, verifySubmission):
# 3-180 caracteres, sin llaves ni saltos de línea adentro. Unificado el 11 oct
# (antes era FLAG{...}) porque el frontend, los retos Wi-Fi del prototipo y el
# comando `ctf submit` de la terminal Kali ya usan WISPR{...}.
# Se valida acá (y no solo "a ojo" en el prompt) porque la IA genera texto,
# no garantías — este regex es la última línea de defensa antes de guardar
# la flag en Supabase.
FLAG_PATTERN = re.compile(r"^WISPR\{[^{}\r\n]{3,180}\}$")

# Registro fijo de técnicas con generador en challenge_generator.py. Agregar
# una técnica = sumarla acá, escribir su generador (con sus 3 niveles y sus
# tests) y sus textos en technique_info.py. Ampliado el 22 oct con 4 técnicas.
TechniqueId = Literal[
    "iv_reuse_wep",
    "xor_singlebyte",
    "caesar_vigenere",
    "encoding_layers",
    "http_plaintext_pcap",
    "stego_png",
]


class ChallengeSpec(BaseModel):
    """
    Especificación de un reto, justo antes de materializarse.

    Desde el 13 oct (guía del ingeniero) la arma el backend: la técnica, la
    dificultad y la flag las decide el código; la IA (Llama 3.3 70B vía
    Together AI) solo aporta la narrativa (`description` y `hint`, ver
    ai_advisor.py). Igual pasa por esta validación: nada llega al generador
    sin ella.

    Ejemplo (ver docs/pipeline_ia_retos.md):
        {
          "id": "crypto-wifi-01",
          "difficulty": "easy",
          "category": "network",
          "description": "Red WEP antigua con reutilización de IVs capturada.",
          "technique": "iv_reuse_wep",
          "flag": "WISPR{wep_died_for_a_reason}",
          "hint": "Busca IVs repetidos en el pcap.",
          "solution": "Extraer IVs duplicados, recuperar keystream, XOR..."
        }
    """

    id: str = Field(..., min_length=1, description="Identificador único del reto, ej. 'crypto-wifi-01'.")

    difficulty: Literal["easy", "medium", "hard"]

    # stego/reverse/misc se agregaron el 13 oct: el dataset del equipo
    # (challenges.json) los usa en ~290 retos, y reclasificarlos a mano no
    # aporta nada. No es un riesgo: lo que decide qué código corre es
    # `technique`, no la categoría.
    category: Literal["web", "crypto", "forensics", "network", "osint", "stego", "reverse", "misc"]

    description: str = Field(
        ..., min_length=1, description="Narrativa del reto que ve el estudiante."
    )

    # Registro fijo de técnicas que el equipo ya programó y probó en
    # challenge_generator.py. Si la IA devuelve cualquier otro valor,
    # Pydantic rechaza el objeto antes de intentar generar nada.
    technique: TechniqueId

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
                f"La flag '{value}' no tiene el formato esperado WISPR{{...}}."
            )
        return value


class DatasetChallenge(BaseModel):
    """
    Un reto del dataset del equipo (`challenges/dataset/`, ~500 ejemplos para
    el LoRA), ya limpio. Misma forma que ChallengeSpec (guía del ingeniero,
    fase 1) con una diferencia a propósito: `technique` acepta "" porque la
    mayoría de esos retos todavía no tiene generador. La explicación en texto
    libre va en `technique_notes`. No se usa para materializar archivos: eso
    sigue exigiendo ChallengeSpec, con su registro fijo.
    """

    id: str = Field(..., min_length=1)
    batch: Literal["manual", "ia"]
    difficulty: Literal["easy", "medium", "hard"]
    category: Literal["web", "crypto", "forensics", "network", "osint", "stego", "reverse", "misc"]
    title: str = Field(..., min_length=3, max_length=90)
    description: str = Field(..., min_length=1)
    technique: Literal[""] | TechniqueId
    technique_notes: str = ""
    flag: str
    hint: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    created_at: str | None = None

    @field_validator("flag")
    @classmethod
    def flag_debe_tener_formato_valido(cls, value: str) -> str:
        if not FLAG_PATTERN.match(value):
            raise ValueError(f"La flag '{value}' no tiene el formato esperado WISPR{{...}}.")
        return value
