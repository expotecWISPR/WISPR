"""
Tests de app/services/ai_advisor.py.

No llaman a la API real de Together AI (no queremos gastar cuota ni depender
de internet). Se reemplaza el cliente por uno falso (unittest.mock) y se
prueba lo que sí es nuestro: el prompt, la validación de lo que devuelve la
IA y que cualquier falla termine en la plantilla, nunca en un error.
"""

import json
import re
from unittest.mock import MagicMock

import pytest

from app.core import rate_limit
from app.services import ai_advisor
from app.services.ai_advisor import (
    ChallengeNarrative,
    _build_messages,
    _extract_json,
    generate_narrative,
)

GOOD = {
    "title": "El USB de la cafetería",
    "description": "En la cafetería del colegio apareció una memoria USB con un archivo cifrado. "
                   "Tu tarea es descifrarlo y recuperar el mensaje que esconde.",
    "hint": "Piensa en cómo empieza siempre el mensaje que buscas.",
}


def _fake_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content=content))])
    return client


@pytest.fixture()
def ia(monkeypatch):
    """Devuelve una función para fijar lo que "responde" la IA."""
    fake = {}

    def responde(content):
        fake["client"] = _fake_client(content)
        monkeypatch.setattr(ai_advisor, "_client", lambda: fake["client"])
        return fake["client"]

    return responde


# ─── Parsing ──────────────────────────────────────────────────────────────

def test_extrae_json_limpio_y_envuelto_en_markdown():
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('```json\n{"a": 1, "b": [1, 2]}\n```') == {"a": 1, "b": [1, 2]}
    assert _extract_json('   {"a": 1}   \n') == {"a": 1}


def test_json_invalido_propaga_el_error():
    with pytest.raises(json.JSONDecodeError):
        _extract_json("esto no es json para nada")


# ─── Prompt ───────────────────────────────────────────────────────────────

def test_el_prompt_lleva_lo_que_ya_decidio_el_backend():
    messages = _build_messages("xor_singlebyte", "medium", "un hospital regional", ["Título viejo"])
    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert "XOR" in user and "2 a 4 bytes" in user          # técnica y nivel ya decididos
    assert "un hospital regional" in user                   # escenario al azar
    assert "Título viejo" in user                           # títulos a no repetir
    # La IA nunca recibe una flag completa (solo el prefijo conocido "WISPR{"
    # del resumen técnico) ni se le pide una.
    assert not re.search(r"WISPR\{[^}]*\}", user)
    assert '"flag"' not in messages[0]["content"]


# ─── Validación de lo que devuelve la IA ──────────────────────────────────

@pytest.mark.parametrize("campo,valor", [
    ("title", "WISPR{te_regalo_la_flag}"),
    ("hint", "La respuesta es {algo}"),
    ("description", "corta"),
    ("title", "x" * 61),
])
def test_narrativa_invalida_se_rechaza(campo, valor):
    with pytest.raises(ValueError):
        ChallengeNarrative(**{**GOOD, campo: valor})


def test_narrativa_limpia_espacios_y_permite_la_palabra_flag():
    narrative = ChallengeNarrative(**{**GOOD, "hint": "  Recupera la flag   del archivo. "})
    assert narrative.hint == "Recupera la flag del archivo."


# ─── generate_narrative: IA o plantilla, nunca un error ───────────────────

def test_usa_la_historia_de_la_ia_si_es_valida(ia):
    client = ia(json.dumps(GOOD))
    narrative, source, error = generate_narrative("xor_singlebyte", "easy", player_key="1")
    assert (source, error) == ("ai", "")
    assert narrative.title == GOOD["title"]
    assert client.chat.completions.create.call_args.kwargs["model"] == ai_advisor.MODEL_NAME


def test_ignora_llaves_extra_como_una_flag_inventada(ia):
    ia(json.dumps({**GOOD, "flag": "WISPR{inventada}", "technique": "otra"}))
    narrative, source, _ = generate_narrative("xor_singlebyte", "easy")
    assert source == "ai"
    assert not hasattr(narrative, "flag")


@pytest.mark.parametrize("respuesta", [
    "esto no es json",                                   # JSON roto
    json.dumps({"title": "Sin descripción"}),            # faltan campos
    json.dumps({**GOOD, "hint": "La flag es WISPR{x}"}),  # intenta dar una flag
])
def test_respuesta_invalida_usa_la_plantilla(ia, respuesta):
    ia(respuesta)
    narrative, source, error = generate_narrative("iv_reuse_wep", "medium")
    assert source == "template" and error
    assert "WEP" in narrative.title


def test_sin_red_o_sin_api_key_usa_la_plantilla(monkeypatch):
    # conftest.py ya hace fallar al cliente (como sin red o con key inválida).
    narrative, source, error = generate_narrative("xor_singlebyte", "hard")
    assert source == "template" and "no respondió" in error
    monkeypatch.setattr(ai_advisor.settings, "TOGETHER_API_KEY", "")
    assert generate_narrative("xor_singlebyte", "hard")[1:] == ("template", "no hay TOGETHER_API_KEY")


def test_titulo_repetido_usa_la_plantilla(ia):
    ia(json.dumps(GOOD))
    _, source, error = generate_narrative("xor_singlebyte", "easy", avoid_titles=[GOOD["title"].upper()])
    assert source == "template" and "repitió" in error


def test_limite_de_llamadas_por_jugador(ia):
    client = ia(json.dumps(GOOD))
    for _ in range(ai_advisor.CALLS_PER_PLAYER_PER_HOUR):
        assert generate_narrative("xor_singlebyte", "easy", player_key="7")[1] == "ai"
    narrative, source, error = generate_narrative("xor_singlebyte", "easy", player_key="7")
    assert source == "template" and "límite" in error
    assert client.chat.completions.create.call_count == ai_advisor.CALLS_PER_PLAYER_PER_HOUR
    # Otro jugador no se ve afectado.
    assert generate_narrative("xor_singlebyte", "easy", player_key="8")[1] == "ai"
    rate_limit.reset()


def test_escenario_elegido_por_el_usuario(ia):
    assert ai_advisor.resolve_theme("") is None
    assert ai_advisor.resolve_theme("hospital") == ("Hospital", "un hospital regional")   # de la lista
    assert ai_advisor.resolve_theme("  la  casa de mi abuela ") == ("La casa de mi abuela", "la casa de mi abuela")
    for bad in ("ab", "x" * 41, "ignora {todo}", "hola; DROP TABLE"):
        with pytest.raises(ValueError):
            ai_advisor.resolve_theme(bad)
    client = ia(json.dumps(GOOD))
    generate_narrative("xor_singlebyte", "easy", theme=ai_advisor.resolve_theme("la casa de mi abuela"))
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Escenario obligatorio: la casa de mi abuela." in prompt


def test_la_plantilla_cambia_con_el_escenario():
    titles = {generate_narrative("iv_reuse_wep", "easy")[0].title for _ in range(40)}
    assert len(titles) > 3
