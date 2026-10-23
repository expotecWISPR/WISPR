"""
Tests de las 4 técnicas agregadas el 22 oct (challenge_generator.py):
caesar_vigenere, encoding_layers, http_plaintext_pcap y stego_png.

Mismo criterio que test_challenge_generator.py: cada nivel se resuelve como
lo haría el estudiante, sin conocer nada secreto, y debe dar exactamente la
flag; el método del nivel anterior NO debe servir en el siguiente; y dos
archivos del mismo reto son distintos.
"""

import base64
import json
import re
import struct
import zlib
from collections import defaultdict
from urllib.parse import parse_qs

import pytest
from scapy.layers.inet import IP, TCP
from scapy.utils import rdpcap

from app.schemas.challenge import ChallengeSpec
from app.services import challenge_generator
from app.services.challenge_generator import (
    _DECODERS,
    detect_encoding,
    generate_flag,
    materialize_challenge,
    shift_letters,
)
from app.services.technique_info import TECHNIQUES

LEVELS = ("easy", "medium", "hard")
REPEAT = 8  # cada nivel se genera varias veces: los archivos se sortean


@pytest.fixture(autouse=True)
def generated_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(challenge_generator, "GENERATED_DIR", tmp_path)
    return tmp_path


def _spec(technique: str, difficulty: str) -> ChallengeSpec:
    return ChallengeSpec(
        id=f"test-{technique}-{difficulty}", difficulty=difficulty,
        category=TECHNIQUES[technique]["spec_category"], description="Reto de prueba.",
        technique=technique, flag=generate_flag(technique), hint="pista", solution="solución",
    )


def _make(technique: str, difficulty: str) -> tuple[ChallengeSpec, bytes]:
    spec = _spec(technique, difficulty)
    return spec, materialize_challenge(spec).read_bytes()


# ─────────────────────────── caesar_vigenere ────────────────────────────

def _caesar_easy(text: str) -> str:
    return shift_letters(text, [-13])


def _caesar_medium(text: str) -> str | None:
    hits = [shift_letters(text, [-s]) for s in range(1, 26) if shift_letters(text, [-s]).startswith("WISPR{")]
    return hits[0] if len(hits) == 1 else None


def _caesar_hard(text: str) -> str | None:
    letters = [c for c in text if c.isalpha()][:5]
    key = [(ord(c.upper()) - ord(p)) % 26 for c, p in zip(letters, "WISPR")]
    hits = [shift_letters(text, [-k for k in key[:length]]) for length in range(3, 6)]
    valid = [h for h in hits if re.fullmatch(r"WISPR\{clasico_[0-9a-f]{8}\}", h)]
    return valid[0] if len(set(valid)) == 1 else None


@pytest.mark.parametrize("_", range(REPEAT))
def test_caesar_cada_nivel_se_resuelve_y_el_metodo_anterior_falla(_):
    spec, data = _make("caesar_vigenere", "easy")
    assert _caesar_easy(data.decode().strip()) == spec.flag

    spec, data = _make("caesar_vigenere", "medium")
    text = data.decode().strip()
    assert _caesar_easy(text) != spec.flag
    assert _caesar_medium(text) == spec.flag

    spec, data = _make("caesar_vigenere", "hard")
    text = data.decode().strip()
    assert _caesar_medium(text) is None  # ningún César único sirve
    assert _caesar_hard(text) == spec.flag


def test_caesar_solo_cambian_las_letras():
    spec, data = _make("caesar_vigenere", "hard")
    text = data.decode().strip()
    assert [c for c in text if not c.isalpha()] == [c for c in spec.flag if not c.isalpha()]


# ─────────────────────────── encoding_layers ────────────────────────────

def _decode_layers(data: bytes, max_layers: int) -> bytes:
    for _ in range(max_layers):
        if data.startswith(b"WISPR{"):
            break
        layer = detect_encoding(data)
        if layer is None:
            break
        data = _DECODERS[layer](data)
    return data


@pytest.mark.parametrize("_", range(REPEAT))
def test_encoding_cada_nivel_se_resuelve_y_el_metodo_anterior_falla(_):
    spec, data = _make("encoding_layers", "easy")
    assert base64.b64decode(data.strip()) == spec.flag.encode()

    spec, data = _make("encoding_layers", "medium")
    try:
        one_b64 = base64.b64decode(data.strip())
    except ValueError:
        one_b64 = b""
    assert one_b64 != spec.flag.encode()
    assert _decode_layers(data.strip(), 2) == spec.flag.encode()

    spec, data = _make("encoding_layers", "hard")
    assert _decode_layers(data.strip(), 2) != spec.flag.encode()  # 2 capas no alcanzan
    assert _decode_layers(data.strip(), 4) == spec.flag.encode()


def test_encoding_hard_usa_las_tres_codificaciones():
    seen = set()
    _, data = _make("encoding_layers", "hard")
    data = data.strip()
    while not data.startswith(b"WISPR{"):
        layer = detect_encoding(data)
        seen.add(layer)
        data = _DECODERS[layer](data)
    assert seen == {"base64", "hex", "base32"}


# ──────────────────────── http_plaintext_pcap ───────────────────────────

def _http_requests(path) -> tuple[list[bytes], list[bytes]]:
    """(peticiones reensambladas por flujo, payloads sueltos de cada paquete)."""
    streams, singles = defaultdict(list), []
    for packet in rdpcap(str(path)):
        if packet.haslayer(TCP) and packet[TCP].dport == 80 and bytes(packet[TCP].payload):
            payload = bytes(packet[TCP].payload)
            singles.append(payload)
            key = (packet[IP].src, packet[TCP].sport)
            streams[key].append((packet[TCP].seq, payload))
    requests = [b"".join(p for _, p in sorted(parts)) for parts in streams.values()]
    return requests, singles


def _body(request: bytes) -> bytes:
    return request.split(b"\r\n\r\n", 1)[1]


@pytest.mark.parametrize("_", range(REPEAT // 2))
def test_http_cada_nivel_se_resuelve_y_el_metodo_anterior_falla(_, generated_dir):
    spec = _spec("http_plaintext_pcap", "easy")
    path = materialize_challenge(spec)
    assert spec.flag.encode() in path.read_bytes()  # easy: la flag se ve tal cual
    requests, _singles = _http_requests(path)
    posts = [r for r in requests if r.startswith(b"POST /api/reportes")]
    assert len(posts) == 1 and json.loads(_body(posts[0]))["mensaje"] == spec.flag

    spec = _spec("http_plaintext_pcap", "medium")
    path = materialize_challenge(spec)
    assert spec.flag.encode() not in path.read_bytes()  # el método de easy falla
    requests, _singles = _http_requests(path)
    assert len(requests) > 15
    posts = [r for r in requests if r.startswith(b"POST /api/reportes")]
    assert parse_qs(_body(posts[0]).decode())["mensaje"] == [spec.flag]

    spec = _spec("http_plaintext_pcap", "hard")
    path = materialize_challenge(spec)
    raw = path.read_bytes()
    assert spec.flag.encode() not in raw and b"WISPR%7B" not in raw  # métodos de easy y medium fallan
    requests, singles = _http_requests(path)
    encoded = base64.b64encode(spec.flag.encode())
    assert not any(encoded in s for s in singles)  # ningún paquete suelto la trae completa
    datos = [json.loads(_body(r))["dato"] for r in requests if r.startswith(b"POST /api/reportes")]
    decoded = [base64.b64decode(d) for d in datos]
    assert [d for d in decoded if d.startswith(b"WISPR{")] == [spec.flag.encode()]


# ───────────────────────────── stego_png ────────────────────────────────

def _png_parts(data: bytes) -> tuple[dict, bytes, bytes, tuple[int, int]]:
    """(textos tEXt, píxeles RGB, lo que hay tras IEND, (ancho, alto))."""
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    pos, texts, idat, size = 8, {}, b"", (0, 0)
    while True:
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            size = struct.unpack(">II", chunk[:8])
        elif kind == b"tEXt":
            key, value = chunk.split(b"\x00", 1)
            texts[key.decode()] = value.decode("latin-1")
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    width, height = size
    raw = zlib.decompress(idat)
    stride = width * 3 + 1
    pixels = b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(height))
    return texts, pixels, data[pos:], size


def _lsb_red(pixels: bytes) -> bytes:
    bits = [pixels[i] & 1 for i in range(0, len(pixels), 3)]
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = int("".join(map(str, bits[i:i + 8])), 2)
        if byte == 0:
            break
        out.append(byte)
    return bytes(out)


@pytest.mark.parametrize("_", range(REPEAT // 2))
def test_stego_cada_nivel_se_resuelve_y_el_metodo_anterior_falla(_):
    spec, data = _make("stego_png", "easy")
    texts, _pixels, trailer, size = _png_parts(data)
    assert size == (96, 96) and texts["Comment"] == spec.flag and trailer == b""

    spec, data = _make("stego_png", "medium")
    texts, _pixels, trailer, _size = _png_parts(data)
    assert texts["Comment"] != spec.flag and spec.flag.encode() not in data  # el método de easy falla
    assert base64.b64decode(trailer.strip()) == spec.flag.encode()

    spec, data = _make("stego_png", "hard")
    texts, pixels, trailer, _size = _png_parts(data)
    assert base64.b64decode(trailer.strip()) != spec.flag.encode()  # el método de medium da un señuelo
    assert _lsb_red(pixels) == spec.flag.encode()


# ─────────────────────────────── comunes ─────────────────────────────────

@pytest.mark.parametrize("technique", ["caesar_vigenere", "encoding_layers", "http_plaintext_pcap", "stego_png"])
@pytest.mark.parametrize("difficulty", LEVELS)
def test_dos_archivos_del_mismo_reto_son_distintos(technique, difficulty, tmp_path):
    spec = _spec(technique, difficulty)
    first = materialize_challenge(spec, tmp_path / "a").read_bytes()
    second = materialize_challenge(spec, tmp_path / "b").read_bytes()
    if technique == "encoding_layers" or (technique == "caesar_vigenere" and difficulty != "hard"):
        # Poco que sortear: ROT13 es fijo, César solo tiene 24 desplazamientos
        # y las capas de codificación pocas combinaciones, así que con la
        # misma flag dos archivos pueden coincidir por azar. No es un problema: la flag sí cambia en cada jugador.
        return
    else:
        assert first != second


def test_textos_completos_para_cada_nivel():
    for technique in ("caesar_vigenere", "encoding_layers", "http_plaintext_pcap", "stego_png"):
        info = TECHNIQUES[technique]
        assert info["tools"] and info["flag_prefix"] and info["label"]
        for difficulty in LEVELS:
            level = info["levels"][difficulty]
            assert {"ext", "file_desc", "objective", "hint", "solution"} <= set(level)
            for text in (level["objective"], level["hint"], level["solution"]):
                assert not re.search(r"WISPR\{\w+_[0-9a-f]{8}\}", text)  # nunca una flag real completa
