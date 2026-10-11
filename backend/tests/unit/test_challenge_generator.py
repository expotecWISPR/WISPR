"""
Tests de app/services/challenge_generator.py.

No alcanza con comprobar que el generador "no explota" — cada técnica acá
se prueba simulando el ataque que haría un estudiante (sin conocer ninguna
llave secreta de antemano) y confirmando que recupera exactamente la flag
del ChallengeSpec. Si estas pruebas pasan, el reto es genuinamente
resoluble, no solo "parece" correcto.
"""

import unittest
from pathlib import Path

from scapy.layers.dot11 import Dot11WEP
from scapy.utils import rdpcap

from app.schemas.challenge import ChallengeSpec
from app.services.challenge_generator import (
    GENERATED_DIR,
    _SNAP_HEADER_ARP,
    _build_known_plaintext,
    generate_wep_reused_iv_pcap,
    generate_xor_challenge,
    materialize_challenge,
)


def _make_spec(**overrides) -> ChallengeSpec:
    base = {
        "id": "test-challenge-01",
        "difficulty": "easy",
        "category": "network",
        "description": "Reto de prueba.",
        "technique": "iv_reuse_wep",
        "flag": "WISPR{test_flag_generica}",
        "hint": "pista",
        "solution": "solucion",
    }
    base.update(overrides)
    return ChallengeSpec(**base)


class _LimpiaArchivosGenerados(unittest.TestCase):
    """Borra cualquier archivo que la prueba haya escrito en GENERATED_DIR."""

    def setUp(self):
        self._archivos_generados: list[Path] = []

    def tearDown(self):
        for path in self._archivos_generados:
            path.unlink(missing_ok=True)

    def _track(self, path: Path) -> Path:
        self._archivos_generados.append(path)
        return path


class TestGenerateWepReusedIvPcap(_LimpiaArchivosGenerados):
    def test_recupera_la_flag_por_reutilizacion_de_iv(self):
        """
        Simula exactamente el ataque descrito en docs/pipeline_ia_retos.md:
        con dos paquetes que comparten IV, XOR contra el plaintext conocido
        (cabecera SNAP + ARP estándar) recupera la flag sin conocer la
        llave WEP.
        """
        spec = _make_spec(id="test-wep-iv-reuse", technique="iv_reuse_wep", flag="WISPR{prueba_wep_iv}")
        path = self._track(generate_wep_reused_iv_pcap(spec))

        self.assertTrue(path.exists())
        self.assertEqual(path.parent, GENERATED_DIR)

        packets = rdpcap(str(path))
        self.assertEqual(len(packets), 2)

        wep1, wep2 = packets[0][Dot11WEP], packets[1][Dot11WEP]
        self.assertEqual(bytes(wep1.iv), bytes(wep2.iv), "los dos paquetes deben reutilizar el mismo IV")

        known_plaintext = _build_known_plaintext(min_len=max(len(wep1.wepdata), len(wep2.wepdata)))
        keystream = bytes(a ^ b for a, b in zip(wep1.wepdata, known_plaintext))
        recovered_plaintext = bytes(a ^ b for a, b in zip(wep2.wepdata, keystream))
        recovered_flag = recovered_plaintext[len(_SNAP_HEADER_ARP):].rstrip(b"\x00").decode("utf-8")

        self.assertEqual(recovered_flag, spec.flag)

    def test_dos_llamadas_generan_llaves_distintas(self):
        """
        Cada reto debe tener su propia llave WEP aleatoria — si dos
        instancias del mismo reto compartieran llave, resolver una
        filtraría la otra.
        """
        spec_a = _make_spec(id="test-wep-a", flag="WISPR{reto_a}")
        spec_b = _make_spec(id="test-wep-b", flag="WISPR{reto_b}")
        path_a = self._track(generate_wep_reused_iv_pcap(spec_a))
        path_b = self._track(generate_wep_reused_iv_pcap(spec_b))

        ciphertext_a = rdpcap(str(path_a))[0][Dot11WEP].wepdata
        ciphertext_b = rdpcap(str(path_b))[0][Dot11WEP].wepdata
        # Mismo plaintext conocido (paquete 1 en ambos), pero llave distinta
        # -> el ciphertext no debería coincidir.
        self.assertNotEqual(bytes(ciphertext_a), bytes(ciphertext_b))


class TestGenerateXorChallenge(_LimpiaArchivosGenerados):
    def test_recupera_la_flag_por_fuerza_bruta(self):
        """
        Simula la fuerza bruta sobre las 256 llaves posibles, sin conocer
        la llave real usada al generar el archivo.
        """
        spec = _make_spec(
            id="test-xor-bruteforce",
            category="crypto",
            technique="xor_singlebyte",
            flag="WISPR{prueba_xor_bruteforce}",
        )
        path = self._track(generate_xor_challenge(spec))
        self.assertTrue(path.exists())

        ciphertext = path.read_bytes()
        recovered = None
        for key in range(256):
            candidate = bytes(b ^ key for b in ciphertext)
            try:
                text = candidate.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if text.startswith("WISPR{") and text.endswith("}"):
                recovered = text
                break

        self.assertEqual(recovered, spec.flag)

    def test_dos_llamadas_generan_llaves_distintas(self):
        spec_a = _make_spec(id="test-xor-a", category="crypto", technique="xor_singlebyte", flag="WISPR{reto_a}")
        spec_b = _make_spec(id="test-xor-b", category="crypto", technique="xor_singlebyte", flag="WISPR{reto_a}")
        path_a = self._track(generate_xor_challenge(spec_a))
        path_b = self._track(generate_xor_challenge(spec_b))
        # Misma flag en ambos specs, pero llaves distintas -> ciphertexts
        # distintos (con probabilidad 255/256 de que la llave no coincida).
        self.assertNotEqual(path_a.read_bytes(), path_b.read_bytes())


class TestMaterializeChallenge(_LimpiaArchivosGenerados):
    def test_despacha_iv_reuse_wep_al_generador_correcto(self):
        spec = _make_spec(id="test-dispatch-wep", technique="iv_reuse_wep")
        path = self._track(materialize_challenge(spec))
        self.assertTrue(path.suffix == ".pcap")

    def test_despacha_xor_singlebyte_al_generador_correcto(self):
        spec = _make_spec(id="test-dispatch-xor", category="crypto", technique="xor_singlebyte")
        path = self._track(materialize_challenge(spec))
        self.assertTrue(path.suffix == ".bin")


if __name__ == "__main__":
    unittest.main()
