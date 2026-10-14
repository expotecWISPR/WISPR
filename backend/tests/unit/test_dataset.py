"""
Dataset de retos del equipo (guía del ingeniero, fase 1): el archivo limpio
(`challenges/dataset/challenges_limpio.json`) valida entero, sin flags ni
títulos repetidos, y la limpieza hace lo que dice con casos chicos.
"""

import json
from pathlib import Path

from app.schemas.challenge import DatasetChallenge
from app.services.dataset_cleaner import clean, rejection_reason

DATASET_DIR = Path(__file__).resolve().parents[3] / "challenges" / "dataset"


def _load(name):
    return json.loads((DATASET_DIR / name).read_text(encoding="utf-8"))


def test_el_dataset_limpio_valida_entero():
    challenges = _load("challenges_limpio.json")["challenges"]
    assert len(challenges) > 200
    for entry in challenges:
        DatasetChallenge(**entry)


def test_sin_flags_ni_titulos_repetidos():
    challenges = _load("challenges_limpio.json")["challenges"]
    flags = [c["flag"] for c in challenges]
    titles = [c["title"].casefold() for c in challenges]
    assert len(flags) == len(set(flags))
    assert len(titles) == len(set(titles))


def test_el_limpio_esta_al_dia_con_el_original():
    """Si alguien cambia el original o el limpiador, hay que volver a correrlo."""
    kept, _ = clean(_load("challenges_original.json"))
    assert kept == _load("challenges_limpio.json")["challenges"]


def _entry(**overrides):
    base = {"id": "x-1", "difficulty": "easy", "category": "crypto", "title": "Reto", "technique": "XOR de un byte",
            "description": "Recibes un archivo cifrado.", "flag": "FLAG{abc_def}", "hint": "h",
            "solution": "Leer el archivo con python, probar las 256 llaves de XOR y quedarse con la legible.",
            "created_at": "2026-10-02T00:00:00+00:00"}
    return {**base, **overrides}


def test_rechaza_soluciones_genericas_del_lote_de_ia():
    assert rejection_reason(_entry()) is None
    assert rejection_reason(_entry(solution="Utiliza herramientas para obtener la flag y listo, sin más.")) is not None
    assert rejection_reason(_entry(solution="Analizar el patrón, identificar los patrones o anomalías, decodificar.")) is not None
    assert rejection_reason(_entry(description="Un sistema raro.", solution="Pensar mucho, probar cosas, ganar.")) is not None


def test_corrige_formato_tecnica_y_duplicados():
    raw = {"challenges": [
        _entry(id="m-1", created_at="2026-09-09T00:00:00+00:00", title="Cifrado", **{"!difficulty": "x"}),
        _entry(id="ia-1", title="Cifrado", flag="FLAG{otra}"),
        _entry(id="ia-2", title="etadata de Imagen", flag="FLAG{abc_def}"),   # flag repetida
    ]}
    kept, report = clean(raw)
    assert [c["id"] for c in kept] == ["m-1", "ia-1"]
    assert kept[0]["flag"] == "WISPR{abc_def}" and kept[0]["batch"] == "manual"
    assert kept[0]["technique"] == "xor_singlebyte" and kept[0]["technique_notes"] == "XOR de un byte"
    assert "!difficulty" not in kept[0]
    assert kept[1]["title"] == "Cifrado II"
    assert report["flags_duplicadas"] == ["ia-2"]
