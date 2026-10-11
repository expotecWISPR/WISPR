"""
Tests de app/schemas/challenge.py (ChallengeSpec).

Estas pruebas verifican la parte más importante del pipeline de IA (ver
docs/pipeline_ia_retos.md): que Pydantic rechace cualquier JSON que no
respete el registro fijo de técnicas o el formato de flag esperado, ANTES
de que ese JSON pueda llegar a challenge_generator.py.
"""

import unittest

from pydantic import ValidationError

from app.schemas.challenge import ChallengeSpec

VALID_SPEC_KWARGS = {
    "id": "crypto-wifi-01",
    "difficulty": "easy",
    "category": "network",
    "description": "Red WEP antigua con reutilización de IVs capturada.",
    "technique": "iv_reuse_wep",
    "flag": "WISPR{wep_died_for_a_reason}",
    "hint": "Busca IVs repetidos en el pcap.",
    "solution": "Extraer IVs duplicados, recuperar keystream, XOR contra ciphertext.",
}


class TestChallengeSpecValido(unittest.TestCase):
    def test_acepta_el_ejemplo_del_pipeline(self):
        spec = ChallengeSpec(**VALID_SPEC_KWARGS)
        self.assertEqual(spec.technique, "iv_reuse_wep")
        self.assertEqual(spec.category, "network")

    def test_acepta_xor_singlebyte(self):
        kwargs = {**VALID_SPEC_KWARGS, "technique": "xor_singlebyte", "category": "crypto"}
        spec = ChallengeSpec(**kwargs)
        self.assertEqual(spec.technique, "xor_singlebyte")


class TestChallengeSpecRechazaTechniqueInvalida(unittest.TestCase):
    def test_rechaza_technique_fuera_del_registro(self):
        """
        Esta es LA prueba de seguridad del pipeline: la IA nunca debe poder
        hacer que se ejecute una técnica que el equipo no construyó.
        """
        kwargs = {**VALID_SPEC_KWARGS, "technique": "sql_injection_magica"}
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)

    def test_rechaza_category_invalida(self):
        kwargs = {**VALID_SPEC_KWARGS, "category": "categoria_que_no_existe"}
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)

    def test_rechaza_difficulty_invalida(self):
        kwargs = {**VALID_SPEC_KWARGS, "difficulty": "imposible"}
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)


class TestChallengeSpecRechazaFlagInvalida(unittest.TestCase):
    def test_rechaza_flag_sin_formato_flag_llaves(self):
        kwargs = {**VALID_SPEC_KWARGS, "flag": "esto-no-tiene-el-formato-correcto"}
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)

    def test_rechaza_flag_vacia_entre_llaves(self):
        kwargs = {**VALID_SPEC_KWARGS, "flag": "WISPR{}"}
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)


class TestChallengeSpecRechazaCamposFaltantes(unittest.TestCase):
    def test_rechaza_si_falta_un_campo_obligatorio(self):
        kwargs = dict(VALID_SPEC_KWARGS)
        del kwargs["flag"]
        with self.assertRaises(ValidationError):
            ChallengeSpec(**kwargs)


if __name__ == "__main__":
    unittest.main()
