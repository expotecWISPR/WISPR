"""
Tests de app/services/ai_advisor.py.

No llaman a la API real de Together AI (no todos en el equipo tienen
TOGETHER_API_KEY todavía, y no queremos gastar cuota ni depender de
internet para correr los tests). En su lugar, se reemplaza el cliente
`Together` por uno falso (unittest.mock) que devuelve una respuesta de
ejemplo, y se prueba la lógica que sí es nuestra: armar el prompt y
parsear la respuesta a un dict que ChallengeSpec pueda validar.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.schemas.challenge import ChallengeSpec
from app.services.ai_advisor import (
    _CATEGORIES,
    _DIFFICULTIES,
    _TECHNIQUES,
    _build_messages,
    _extract_json,
    generate_challenge_spec_raw,
)


class TestExtractJson(unittest.TestCase):
    def test_extrae_json_limpio(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_extrae_json_envuelto_en_fences_de_markdown(self):
        """
        Los LLM a veces devuelven ```json ... ``` aunque el prompt les pida
        explícitamente no hacerlo — esto no debería romper el parsing.
        """
        wrapped = '```json\n{"a": 1, "b": [1, 2]}\n```'
        self.assertEqual(_extract_json(wrapped), {"a": 1, "b": [1, 2]})

    def test_extrae_json_con_espacios_alrededor(self):
        self.assertEqual(_extract_json('   {"a": 1}   \n'), {"a": 1})

    def test_json_invalido_propaga_el_error(self):
        """
        Un JSON roto debe fallar de forma visible (json.JSONDecodeError),
        nunca devolver silenciosamente algo a medio parsear.
        """
        import json

        with self.assertRaises(json.JSONDecodeError):
            _extract_json("esto no es json para nada")


class TestBuildMessages(unittest.TestCase):
    def test_incluye_las_tecnicas_del_registro_fijo_en_el_prompt(self):
        messages = _build_messages("network", "easy")
        system_content = messages[0]["content"]
        for technique in _TECHNIQUES:
            self.assertIn(technique, system_content)

    def test_estructura_de_roles(self):
        messages = _build_messages("crypto", "medium")
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertIn("crypto", messages[1]["content"])
        self.assertIn("medium", messages[1]["content"])


class TestListasSincronizadasConChallengeSpec(unittest.TestCase):
    """
    Si alguien agrega una técnica/categoría/dificultad nueva a ChallengeSpec
    y se olvida de que ai_advisor.py lee esas mismas listas (no las
    duplica a mano), estas pruebas lo detectan.
    """

    def test_technicas_coinciden_con_el_schema(self):
        from typing import get_args

        esperado = get_args(ChallengeSpec.model_fields["technique"].annotation)
        self.assertEqual(set(_TECHNIQUES), set(esperado))

    def test_categorias_coinciden_con_el_schema(self):
        from typing import get_args

        esperado = get_args(ChallengeSpec.model_fields["category"].annotation)
        self.assertEqual(set(_CATEGORIES), set(esperado))

    def test_dificultades_coinciden_con_el_schema(self):
        from typing import get_args

        esperado = get_args(ChallengeSpec.model_fields["difficulty"].annotation)
        self.assertEqual(set(_DIFFICULTIES), set(esperado))


def _fake_together_client(response_content: str) -> MagicMock:
    """Arma un cliente Together falso cuyo chat.completions.create(...) devuelve `response_content`."""
    fake_message = MagicMock(content=response_content)
    fake_choice = MagicMock(message=fake_message)
    fake_response = MagicMock(choices=[fake_choice])

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    return fake_client


class TestGenerateChallengeSpecRaw(unittest.TestCase):
    @patch("app.services.ai_advisor.Together")
    def test_devuelve_un_dict_valido_para_challengespec(self, mock_together_cls):
        fake_json = """{
            "id": "network-wep-99",
            "difficulty": "easy",
            "category": "network",
            "description": "Red WEP vulnerable",
            "technique": "iv_reuse_wep",
            "flag": "FLAG{simulado_por_test}",
            "hint": "IVs repetidos",
            "solution": "XOR contra plaintext conocido"
        }"""
        mock_together_cls.return_value = _fake_together_client(fake_json)

        raw = generate_challenge_spec_raw("network", "easy")

        self.assertEqual(raw["technique"], "iv_reuse_wep")
        # El punto clave: lo que devuelve esta función debe poder pasar
        # directo a ChallengeSpec sin transformación adicional.
        spec = ChallengeSpec(**raw)
        self.assertEqual(spec.flag, "FLAG{simulado_por_test}")

    @patch("app.services.ai_advisor.Together")
    def test_tolera_respuesta_envuelta_en_markdown(self, mock_together_cls):
        fake_json_wrapped = """```json
        {
            "id": "crypto-xor-99",
            "difficulty": "easy",
            "category": "crypto",
            "description": "desc",
            "technique": "xor_singlebyte",
            "flag": "FLAG{con_markdown}",
            "hint": "hint",
            "solution": "sol"
        }
        ```"""
        mock_together_cls.return_value = _fake_together_client(fake_json_wrapped)

        raw = generate_challenge_spec_raw("crypto", "easy")
        spec = ChallengeSpec(**raw)
        self.assertEqual(spec.flag, "FLAG{con_markdown}")


if __name__ == "__main__":
    unittest.main()
