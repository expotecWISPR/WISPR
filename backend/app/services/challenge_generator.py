"""
Generador determinista de archivos de retos (materialización).

Este módulo es la segunda mitad del pipeline de generación de retos con IA
(ver docs/pipeline_ia_retos.md). Recibe un ChallengeSpec ya validado por
Pydantic y construye el archivo real del reto. La IA nunca ejecuta código ni
genera bytes directamente; tampoco decide la técnica, la dificultad ni la
flag (guía del ingeniero, 12 oct): eso lo decide el backend.

Flujo:
    ChallengeSpec (ya validado por app/schemas/challenge.py)
        -> TECHNIQUE_REGISTRY[spec.technique]
        -> función generadora específica de esta técnica
        -> archivo real (por jugador: ver app/services/instances.py)

Dificultad real (12 oct): cada generador lee `spec.difficulty` y cambia el
archivo, no solo los puntos. Los parámetros de cada nivel están en las
tablas XOR_LEVELS y WEP_LEVELS de abajo, escritas en el código (no en el
prompt). Además, todo lo que antes era fijo (IV, MACs, llaves) se sortea en
cada generación: dos archivos del mismo reto nunca son iguales.

TODO (fuera de este alcance, ver CLAUDE.md punto 9): subir el archivo
resultante a S3 en vez de dejarlo en disco local. Por ahora se escribe en
challenges/generated/, que ya está en .gitignore.
"""

import base64
import os
import random
import secrets
from pathlib import Path

from scapy.layers.dot11 import Dot11, Dot11WEP, RadioTap
from scapy.layers.l2 import ARP
from scapy.utils import wrpcap

from app.schemas.challenge import ChallengeSpec
from app.services.technique_info import KNOWN_ARP_DST_IP, KNOWN_ARP_SRC_IP, TECHNIQUES

GENERATED_DIR = Path(__file__).resolve().parents[3] / "challenges" / "generated"

# `random.SystemRandom` usa el generador del sistema operativo (igual que
# `secrets`): ningún jugador puede predecir el archivo de otro.
_rng = random.SystemRandom()


def generate_flag(technique: str) -> str:
    """
    Flag nueva e imposible de adivinar, ej. WISPR{xor_9f3a01c2}. La genera el
    backend con `secrets`, nunca la IA: así no se repite entre jugadores ni
    revela la respuesta (la guía encontró flags como FLAG{vigenere_is_weak}).
    """
    return f"WISPR{{{TECHNIQUES[technique]['flag_prefix']}_{secrets.token_hex(4)}}}"


def _random_mac() -> str:
    # Unicast y "administrada localmente" (bit 1 del primer byte en 1): no
    # choca con el fabricante real de ninguna tarjeta.
    first = (_rng.randrange(256) & 0xFC) | 0x02
    return ":".join(f"{b:02x}" for b in [first, *(_rng.randrange(256) for _ in range(5))])


def _default_path(spec: ChallengeSpec) -> Path:
    ext = TECHNIQUES[spec.technique]["levels"][spec.difficulty]["ext"]
    return GENERATED_DIR / f"{spec.id}.{ext}"


# ─────────────────────────────────────────────────────────────────────────
# RC4 — el cifrado de flujo que usa WEP
# ─────────────────────────────────────────────────────────────────────────
# WEP cifra cada paquete con RC4, usando como llave el IV (3 bytes, viaja
# en claro dentro del paquete) concatenado con la llave WEP secreta. Se
# implementa acá a mano en vez de traer una librería de criptografía
# porque: (1) son ~15 líneas, no justifica una dependencia nueva, y
# (2) RC4 ya fue retirado de librerías modernas (ej. `cryptography`) por
# inseguro — que es justamente el punto pedagógico del reto: entender por
# qué WEP/RC4 se dejaron de usar.
def _rc4_keystream(key: bytes, length: int) -> bytes:
    """Genera `length` bytes de keystream RC4 para `key` (KSA + PRGA)."""
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]

    keystream = bytearray()
    i = j = 0
    for _ in range(length):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        keystream.append(S[(S[i] + S[j]) % 256])
    return bytes(keystream)


def _rc4_crypt(key: bytes, data: bytes) -> bytes:
    """Cifra (o descifra — RC4 es simétrico) `data` con la llave `key`."""
    keystream = _rc4_keystream(key, len(data))
    return bytes(a ^ b for a, b in zip(data, keystream))


# ─────────────────────────────────────────────────────────────────────────
# iv_reuse_wep — reto de reutilización de IV en WEP
# ─────────────────────────────────────────────────────────────────────────
# Cabecera LLC/SNAP para tráfico ARP encapsulado en 802.11: siempre son los
# mismos 8 bytes para cualquier paquete ARP (estándar IEEE 802.2). No es un
# secreto del reto — es justo el "known plaintext" que ataques reales de
# WEP (y aircrack-ng) usan para recuperar keystream por reutilización de IV.
_SNAP_HEADER_ARP = bytes.fromhex("aaaa03000000") + b"\x08\x06"
# Mismo encabezado, pero para IPv4: es el "ruido" (tráfico normal de la red).
_SNAP_HEADER_IP = bytes.fromhex("aaaa03000000") + b"\x08\x00"

# Niveles (guía del ingeniero, fase 2):
#   easy   -> solo las 2 tramas del ataque.
#   medium -> el par escondido entre 20-50 tramas de ruido; el ARP va primero.
#   hard   -> entre 200-400 tramas; el ARP lo manda el AP (no la estación) y
#             va DESPUÉS de la flag. Como el texto conocido incluye la MAC de
#             origen del ARP, quien asuma "la primera del par es el ARP"
#             (método de medium) arma un texto conocido equivocado y saca
#             basura. Hay que reconocer el ARP por su largo (36 bytes).
# (El orden solo no alcanzaría: c1 XOR c2 = p1 XOR p2, da igual cuál se
# trate como "conocido" si los dos salen de la misma MAC.)
WEP_LEVELS = {
    "easy": {"noise": (0, 0), "arp_from_ap": False},
    "medium": {"noise": (20, 50), "arp_from_ap": False},
    "hard": {"noise": (200, 400), "arp_from_ap": True},
}


def _build_known_plaintext(sta_mac: str, min_len: int = 0) -> bytes:
    """
    Arma el paquete conocido: SNAP + un ARP request desde `sta_mac` (la MAC
    de origen de la trama, que viaja en claro), con las IPs documentadas en
    el objetivo del reto (technique_info.py). El jugador puede reconstruir
    este plaintext exacto sin descifrar nada — es la mitad "conocida" del
    ataque. Se rellena con ceros si la flag es más larga que el ARP.
    """
    known_arp = ARP(
        hwtype=1, ptype=0x0800, hwlen=6, plen=4, op=1,
        hwsrc=sta_mac, psrc=KNOWN_ARP_SRC_IP,
        hwdst="00:00:00:00:00:00", pdst=KNOWN_ARP_DST_IP,
    )
    plaintext = _SNAP_HEADER_ARP + bytes(known_arp)
    if len(plaintext) < min_len:
        plaintext += b"\x00" * (min_len - len(plaintext))
    return plaintext


def generate_wep_reused_iv_pcap(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    """
    Genera un .pcap con tramas 802.11 WEP donde exactamente dos reutilizan
    el mismo IV:

    - El ARP conocido (SNAP + ARP request), documentado en el objetivo.
    - La flag (SNAP + flag), cifrada con el MISMO IV.

    Como RC4(IV+key) produce el mismo keystream para ambos paquetes, el
    estudiante recupera la flag sin conocer la llave WEP:

        keystream   = ciphertext_arp XOR plaintext_arp_conocido
        plaintext_2 = ciphertext_flag XOR keystream

    El resto de las tramas (según el nivel) es ruido con IVs distintos.

    Nota de alcance: se omite el ICV (CRC32) real de WEP a propósito — no
    aporta nada a la vulnerabilidad enseñada (reutilización de IV) y solo
    agregaría complejidad sin valor pedagógico.
    """
    level = WEP_LEVELS[spec.difficulty]
    ap_mac, sta_mac = _random_mac(), _random_mac()
    wep_key = os.urandom(5)  # WEP-40, distinta en cada archivo. El estudiante nunca la necesita.

    flag_plaintext = _SNAP_HEADER_ARP + spec.flag.encode("utf-8")
    arp_from_ap = level["arp_from_ap"]
    known_plaintext = _build_known_plaintext(ap_mac if arp_from_ap else sta_mac, min_len=len(flag_plaintext))

    noise_count = _rng.randint(*level["noise"])
    # IVs todos distintos entre sí: el único IV repetido es el del ataque.
    ivs: set[bytes] = set()
    while len(ivs) < noise_count + 1:
        ivs.add(os.urandom(3))
    reused_iv, *noise_ivs = list(ivs)

    def _frame(iv: bytes, plaintext: bytes, from_ap: bool = False) -> object:
        src, dst = (ap_mac, sta_mac) if from_ap else (sta_mac, ap_mac)
        return (
            RadioTap()
            / Dot11(type=2, subtype=0, FCfield="protected", addr1=dst, addr2=src, addr3=ap_mac)
            / Dot11WEP(iv=iv, keyid=0, wepdata=_rc4_crypt(iv + wep_key, plaintext), icv=0)
        )

    frames = [
        _frame(iv, _SNAP_HEADER_IP + os.urandom(_rng.randint(32, 180)), from_ap=_rng.random() < 0.5)
        for iv in noise_ivs
    ]
    pair = [_frame(reused_iv, known_plaintext, from_ap=arp_from_ap), _frame(reused_iv, flag_plaintext)]
    if arp_from_ap:
        pair.reverse()
    # Posiciones al azar, respetando el orden del par.
    first_pos = _rng.randint(0, len(frames))
    frames.insert(first_pos, pair[0])
    frames.insert(_rng.randint(first_pos + 1, len(frames)), pair[1])

    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(output_path), frames)
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# xor_singlebyte — reto de XOR (categoría crypto)
# ─────────────────────────────────────────────────────────────────────────
# El nombre viene del nivel easy (llave de un byte, 256 posibilidades, la
# lección de por qué una llave tan corta no sirve). En medium y hard la llave
# es más larga y la fuerza bruta de 256 ya no funciona: hay que usar texto
# conocido (toda flag empieza con "WISPR{", 6 bytes), así que la llave nunca
# pasa de 6 bytes — el reto siempre se puede resolver.
XOR_LEVELS = {
    "easy": {"key_len": (1, 1), "encoding": "raw"},
    "medium": {"key_len": (2, 4), "encoding": "raw"},
    "hard": {"key_len": (5, 6), "encoding": "base64"},
}


def _xor_key(length: int) -> bytes:
    # Bytes 1-255 (un 0 dejaría letras de la flag a la vista) y, si es más de
    # 1 byte, no todos iguales (sería una llave de 1 byte disfrazada y la
    # fuerza bruta de easy volvería a funcionar).
    while True:
        key = bytes(_rng.randint(1, 255) for _ in range(length))
        if length == 1 or len(set(key)) > 1:
            return key


def generate_xor_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    """
    Genera el archivo con la flag cifrada por XOR contra una llave aleatoria
    que se repite. El largo de la llave y la codificación dependen del nivel
    (XOR_LEVELS). En easy, el estudiante prueba las 256 llaves:

        para cada llave en 0..255:
            texto = bytes(b ^ llave for b in ciphertext)
            si empieza con "WISPR{" -> esa es la flag
    """
    level = XOR_LEVELS[spec.difficulty]
    key = _xor_key(_rng.randint(*level["key_len"]))
    plaintext = spec.flag.encode("utf-8")
    ciphertext = bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext))
    if level["encoding"] == "base64":
        ciphertext = base64.b64encode(ciphertext) + b"\n"

    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(ciphertext)
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# Registro de técnicas — la pieza que le da seguridad al pipeline
# ─────────────────────────────────────────────────────────────────────────
# Solo se puede materializar una `technique` que ya esté en este diccionario
# (reforzado también por el Literal en ChallengeSpec — ver ese archivo).
# Agregar una técnica nueva implica: 1) sumarla al Literal en
# app/schemas/challenge.py, 2) escribir y probar su función generadora
# acá, con sus niveles easy/medium/hard, 3) registrarla en este diccionario,
# 4) escribir sus textos en technique_info.py.
TECHNIQUE_REGISTRY = {
    "iv_reuse_wep": generate_wep_reused_iv_pcap,
    "xor_singlebyte": generate_xor_challenge,
}


def materialize_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    """
    Punto de entrada del generador determinista: recibe un ChallengeSpec ya
    validado por Pydantic y devuelve la ruta del archivo real generado.
    Sin `output_path`, escribe en challenges/generated/<id>.<ext>.
    """
    generator = TECHNIQUE_REGISTRY[spec.technique]
    return generator(spec, output_path)
