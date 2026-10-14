"""
Tests de app/services/challenge_generator.py.

No alcanza con comprobar que el generador "no explota" — cada técnica y
cada nivel se prueba simulando el ataque que haría un estudiante (sin
conocer ninguna llave secreta de antemano) y confirmando que recupera
exactamente la flag del ChallengeSpec. Además (guía del ingeniero, fase 2):
el método del nivel anterior NO debe servir en el siguiente, y dos archivos
del mismo reto deben ser distintos.
"""

import base64
import re
from collections import defaultdict

import pytest
from scapy.layers.dot11 import Dot11, Dot11WEP
from scapy.utils import rdpcap

from app.schemas.challenge import ChallengeSpec
from app.services import challenge_generator
from app.services.challenge_generator import (
    _SNAP_HEADER_ARP,
    _build_known_plaintext,
    generate_flag,
    generate_wep_reused_iv_pcap,
    generate_xor_challenge,
    materialize_challenge,
)

FLAG_RE = re.compile(rb"^WISPR\{[^{}\r\n]{3,180}\}$")


@pytest.fixture(autouse=True)
def generated_dir(tmp_path, monkeypatch):
    """Los archivos de prueba van a una carpeta temporal, no a challenges/generated/."""
    monkeypatch.setattr(challenge_generator, "GENERATED_DIR", tmp_path)
    return tmp_path


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


def _xor_spec(difficulty: str, flag: str = "WISPR{xor_prueba_123}") -> ChallengeSpec:
    return _make_spec(id=f"test-xor-{difficulty}", category="crypto", technique="xor_singlebyte",
                      difficulty=difficulty, flag=flag)


def _wep_spec(difficulty: str, flag: str = "WISPR{wep_prueba_123}") -> ChallengeSpec:
    return _make_spec(id=f"test-wep-{difficulty}", difficulty=difficulty, flag=flag)


# ─── Solvers: lo que haría el estudiante en cada nivel ────────────────────

def _xor_bruteforce_1_byte(data: bytes) -> bytes | None:
    """Método de easy: probar las 256 llaves de un byte."""
    for key in range(256):
        candidate = bytes(b ^ key for b in data)
        if FLAG_RE.match(candidate):
            return candidate
    return None


def _xor_known_plaintext(data: bytes, max_len: int) -> bytes | None:
    """Método de medium/hard: llave = cifrado XOR 'WISPR{', probando largos."""
    known = b"WISPR{"
    for length in range(1, max_len + 1):
        key = bytes(data[i] ^ known[i] for i in range(min(length, len(known))))
        if len(key) < length:
            continue
        candidate = bytes(b ^ key[i % length] for i, b in enumerate(data))
        if FLAG_RE.match(candidate):
            return candidate
    return None


def _wep_pairs(packets) -> list:
    by_iv = defaultdict(list)
    for pkt in packets:
        by_iv[bytes(pkt[Dot11WEP].iv)].append(pkt)
    repeated = [group for group in by_iv.values() if len(group) > 1]
    assert len(repeated) == 1, "debe haber exactamente un IV repetido"
    return repeated[0]


def _wep_recover(known_pkt, flag_pkt) -> bytes:
    known = _build_known_plaintext(known_pkt[Dot11].addr2, min_len=len(flag_pkt[Dot11WEP].wepdata))
    keystream = bytes(a ^ b for a, b in zip(known_pkt[Dot11WEP].wepdata, known))
    plaintext = bytes(a ^ b for a, b in zip(flag_pkt[Dot11WEP].wepdata, keystream))
    return plaintext[len(_SNAP_HEADER_ARP):].rstrip(b"\x00")


# ─── XOR ──────────────────────────────────────────────────────────────────

def test_xor_easy_se_resuelve_por_fuerza_bruta():
    spec = _xor_spec("easy")
    data = generate_xor_challenge(spec).read_bytes()
    assert _xor_bruteforce_1_byte(data) == spec.flag.encode()


@pytest.mark.parametrize("_", range(5))  # la llave es al azar: varias corridas
def test_xor_medium_no_cae_con_fuerza_bruta_pero_si_con_texto_conocido(_):
    spec = _xor_spec("medium")
    data = generate_xor_challenge(spec).read_bytes()
    assert _xor_bruteforce_1_byte(data) is None
    assert _xor_known_plaintext(data, max_len=4) == spec.flag.encode()


@pytest.mark.parametrize("_", range(5))
def test_xor_hard_esta_en_base64_y_se_resuelve_decodificando_primero(_):
    spec = _xor_spec("hard")
    data = generate_xor_challenge(spec).read_bytes()
    # Ni el método de easy ni el de medium sirven sobre el archivo tal cual.
    assert _xor_bruteforce_1_byte(data) is None
    assert _xor_known_plaintext(data, max_len=4) is None
    decoded = base64.b64decode(data)
    assert _xor_bruteforce_1_byte(decoded) is None
    assert _xor_known_plaintext(decoded, max_len=6) == spec.flag.encode()


# ─── WEP ──────────────────────────────────────────────────────────────────

def test_wep_easy_dos_tramas_mismo_iv():
    spec = _wep_spec("easy")
    packets = rdpcap(str(generate_wep_reused_iv_pcap(spec)))
    assert len(packets) == 2
    assert bytes(packets[0][Dot11WEP].iv) == bytes(packets[1][Dot11WEP].iv)
    assert _wep_recover(packets[0], packets[1]) == spec.flag.encode()


def test_wep_medium_esconde_el_par_entre_ruido():
    spec = _wep_spec("medium")
    packets = rdpcap(str(generate_wep_reused_iv_pcap(spec)))
    assert 22 <= len(packets) <= 52
    known, flag = _wep_pairs(packets)          # en medium, el ARP va primero
    assert _wep_recover(known, flag) == spec.flag.encode()


def test_wep_hard_el_metodo_de_medium_no_sirve():
    spec = _wep_spec("hard")
    packets = rdpcap(str(generate_wep_reused_iv_pcap(spec)))
    assert 202 <= len(packets) <= 402
    first, second = _wep_pairs(packets)
    # "La primera del par es el ARP" (medium) da basura en hard.
    assert _wep_recover(first, second) != spec.flag.encode()
    # Identificando el ARP por su largo (36 bytes), sí sale.
    arp = first if len(first[Dot11WEP].wepdata) == 36 else second
    other = second if arp is first else first
    assert _wep_recover(arp, other) == spec.flag.encode()


# ─── Variedad: dos generaciones nunca dan el mismo archivo ─────────────────

@pytest.mark.parametrize("technique,difficulty", [
    ("xor_singlebyte", "medium"), ("xor_singlebyte", "hard"),
    ("iv_reuse_wep", "easy"), ("iv_reuse_wep", "medium"),
])
def test_mismo_reto_dos_veces_da_archivos_distintos(tmp_path, technique, difficulty):
    category = "crypto" if technique == "xor_singlebyte" else "network"
    spec = _make_spec(technique=technique, category=category, difficulty=difficulty)
    a = materialize_challenge(spec, tmp_path / "a" / "f").read_bytes()
    b = materialize_challenge(spec, tmp_path / "b" / "f").read_bytes()
    assert a != b


def test_wep_sortea_iv_y_macs_en_cada_archivo(tmp_path):
    spec = _wep_spec("easy")
    first = rdpcap(str(materialize_challenge(spec, tmp_path / "a.pcap")))[0]
    second = rdpcap(str(materialize_challenge(spec, tmp_path / "b.pcap")))[0]
    assert (bytes(first[Dot11WEP].iv), first[Dot11].addr2) != (bytes(second[Dot11WEP].iv), second[Dot11].addr2)


# ─── Flags y despacho ─────────────────────────────────────────────────────

def test_generate_flag_es_valida_y_no_se_repite():
    flags = {generate_flag("xor_singlebyte") for _ in range(200)}
    assert len(flags) == 200
    for flag in flags:
        assert re.fullmatch(r"WISPR\{xor_[0-9a-f]{8}\}", flag)
    assert generate_flag("iv_reuse_wep").startswith("WISPR{wep_")


def test_materialize_usa_la_extension_del_nivel(generated_dir):
    assert materialize_challenge(_wep_spec("easy")).name == "test-wep-easy.pcap"
    assert materialize_challenge(_xor_spec("easy")).suffix == ".bin"
    assert materialize_challenge(_xor_spec("hard")).suffix == ".txt"
    assert materialize_challenge(_xor_spec("easy")).parent == generated_dir
