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
tablas *_LEVELS de abajo (XOR, WEP y, desde el 22 oct, CAESAR, ENCODING,
HTTP y STEGO), escritas en el código (no en el prompt). Además, todo lo que antes era fijo (IV, MACs, llaves) se sortea en
cada generación: dos archivos del mismo reto nunca son iguales.

TODO (fuera de este alcance, ver CLAUDE.md punto 9): subir el archivo
resultante a S3 en vez de dejarlo en disco local. Por ahora se escribe en
challenges/generated/, que ya está en .gitignore.
"""

import base64
import os
import random
import re
import secrets
import struct
import zlib
from pathlib import Path
from urllib.parse import quote

from scapy.layers.dot11 import Dot11, Dot11WEP, RadioTap
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import ARP, Ether
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
# caesar_vigenere — criptografía clásica (22 oct)
# ─────────────────────────────────────────────────────────────────────────
# Solo se desplazan las letras (mayúsculas y minúsculas por separado); los
# dígitos, "_" y las llaves quedan igual. En Vigenère la llave avanza solo con
# las letras. Toda flag empieza con "WISPR" (5 letras conocidas), así que la
# llave de hard nunca pasa de 5 letras: el reto siempre se puede resolver.
#   easy   -> ROT13 (desplazamiento 13, conocido).
#   medium -> César con desplazamiento al azar, nunca 13: ROT13 ya no sirve.
#   hard   -> Vigenère con llave de 3 a 5 letras no todas iguales: ningún
#             desplazamiento único (método de medium) recupera "WISPR".
CAESAR_LEVELS = {
    "easy": {"mode": "rot13"},
    "medium": {"mode": "caesar"},
    "hard": {"mode": "vigenere", "key_len": (3, 5)},
}


def shift_letters(text: str, shifts: list[int]) -> str:
    """Desplaza cada letra según `shifts` (cíclico, solo cuenta las letras). Con -s descifra."""
    out, j = [], 0
    for char in text:
        if char.isascii() and char.isalpha():
            base = ord("A") if char.isupper() else ord("a")
            out.append(chr((ord(char) - base + shifts[j % len(shifts)]) % 26 + base))
            j += 1
        else:
            out.append(char)
    return "".join(out)


def _caesar_shifts(difficulty: str) -> list[int]:
    level = CAESAR_LEVELS[difficulty]
    if level["mode"] == "rot13":
        return [13]
    if level["mode"] == "caesar":
        return [_rng.choice([s for s in range(1, 26) if s != 13])]
    while True:  # sin desplazamiento 0 (dejaría letras a la vista) y no todas iguales
        key = [_rng.randint(1, 25) for _ in range(_rng.randint(*level["key_len"]))]
        if len(set(key)) > 1:
            return key


def generate_caesar_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    ciphertext = shift_letters(spec.flag, _caesar_shifts(spec.difficulty))
    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ciphertext + "\n", encoding="ascii")
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# encoding_layers — capas de codificación (22 oct)
# ─────────────────────────────────────────────────────────────────────────
# Codificar NO es cifrar: no hay llave, solo hay que reconocer cada formato.
#   easy   -> 1 capa de base64.
#   medium -> 2 capas distintas (base64, hex o base32) en orden al azar: un
#             solo base64 -d ya no alcanza.
#   hard   -> 3 o 4 capas, sin repetir dos seguidas y usando las tres.
# Cada capa se reconoce por su alfabeto (ver `detect_encoding`). Antes de
# guardar, el generador decodifica como lo haría el estudiante y, si alguna
# capa fuera ambigua, vuelve a sortear: el archivo siempre es resoluble.
ENCODING_LEVELS = {
    "easy": {"layers": (1, 1)},
    "medium": {"layers": (2, 2)},
    "hard": {"layers": (3, 4)},
}
_ENCODERS = {
    "base64": lambda data: base64.b64encode(data),
    "hex": lambda data: data.hex().encode("ascii"),
    "base32": lambda data: base64.b32encode(data),
}
_DECODERS = {
    "base64": base64.b64decode,
    "hex": lambda data: bytes.fromhex(data.decode("ascii")),
    "base32": base64.b32decode,
}


def detect_encoding(data: bytes) -> str | None:
    """Reconoce la capa por su alfabeto, como se le enseña al estudiante:
    hex = 0-9 a-f; base32 = A-Z 2-7 y relleno '='; base64 = el resto."""
    text = data.decode("ascii", errors="replace")
    if len(text) % 2 == 0 and re.fullmatch(r"[0-9a-f]+", text):
        return "hex"
    if len(text) % 8 == 0 and re.fullmatch(r"[A-Z2-7]+=*", text):
        return "base32"
    if len(text) % 4 == 0 and re.fullmatch(r"[A-Za-z0-9+/]+=*", text):
        return "base64"
    return None


def _layer_plan(difficulty: str) -> list[str]:
    count = _rng.randint(*ENCODING_LEVELS[difficulty]["layers"])
    if count == 1:
        return ["base64"]
    while True:
        plan = [_rng.choice(list(_ENCODERS)) for _ in range(count)]
        consecutive = any(a == b for a, b in zip(plan, plan[1:]))
        if not consecutive and (count < 3 or len(set(plan)) == 3):
            return plan


def generate_encoding_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    flag = spec.flag.encode("utf-8")
    for _ in range(50):
        data = flag
        for layer in _layer_plan(spec.difficulty):
            data = _ENCODERS[layer](data)
        # Verificación: decodificar reconociendo cada capa debe dar la flag.
        probe = data
        try:
            while not probe.startswith(b"WISPR{") and (layer := detect_encoding(probe)):
                probe = _DECODERS[layer](probe)
        except ValueError:  # una capa mal reconocida (binascii.Error también es ValueError)
            continue
        if probe == flag:
            break
    else:  # pragma: no cover — 50 sorteos ambiguos seguidos no ocurren en la práctica
        raise RuntimeError("No se pudo generar una cadena de codificaciones inequívoca.")
    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data + b"\n")
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# http_plaintext_pcap — información sensible en HTTP sin cifrar (22 oct)
# ─────────────────────────────────────────────────────────────────────────
# Lección: lo que viaja por HTTP (sin TLS) se lee entero en una captura.
#   easy   -> una sola petición POST con la flag a la vista en JSON.
#   medium -> la petición con la flag entre 15-30 sesiones de ruido, con la
#             flag codificada en URL (WISPR%7B…%7D): buscar "WISPR{" en el
#             archivo (método de easy) no la encuentra.
#   hard   -> la flag en base64 dentro de un campo JSON, con la petición
#             PARTIDA en 2 segmentos TCP y otras peticiones señuelo con base64
#             que no es la flag. Hay que reensamblar el flujo (Follow TCP
#             Stream) y decodificar.
HTTP_LEVELS = {
    "easy": {"noise": (0, 0), "style": "json"},
    "medium": {"noise": (15, 30), "style": "urlencoded"},
    "hard": {"noise": (25, 45), "style": "split_base64"},
}
_HTTP_PAGES = ["/", "/index.html", "/horarios", "/noticias", "/css/estilo.css", "/img/logo.png", "/contacto"]
_HTTP_DECOYS = ["horario de laboratorio", "reporte semanal", "inventario de equipos", "lista de asistencia"]


def _private_ip(prefix: str) -> str:
    return f"{prefix}.{_rng.randint(2, 250)}"


def _http_session(client: str, server: str, request: bytes, response: bytes, split_at: int | None = None) -> list:
    """Una conexión TCP completa: saludo de 3 pasos, la petición (entera, o
    partida en `split_at` en 2 segmentos con números de secuencia correctos)
    y la respuesta."""
    sport, cseq, sseq = _rng.randint(40000, 60000), _rng.randrange(2**31), _rng.randrange(2**31)
    c2s = lambda flags, seq, ack, data=b"": IP(src=client, dst=server) / TCP(sport=sport, dport=80, flags=flags, seq=seq, ack=ack) / data  # noqa: E731
    s2c = lambda flags, seq, ack, data=b"": IP(src=server, dst=client) / TCP(sport=80, dport=sport, flags=flags, seq=seq, ack=ack) / data  # noqa: E731
    packets = [c2s("S", cseq, 0), s2c("SA", sseq, cseq + 1), c2s("A", cseq + 1, sseq + 1)]
    cut = [0, len(request)] if split_at is None else [0, split_at, len(request)]
    for start, end in zip(cut, cut[1:]):
        packets.append(c2s("PA", cseq + 1 + start, sseq + 1, request[start:end]))
    packets.append(s2c("PA", sseq + 1, cseq + 1 + len(request), response))
    packets.append(c2s("A", cseq + 1 + len(request), sseq + 1 + len(response)))
    return packets


def _http_post(host: str, path: str, body: bytes, content_type: str) -> bytes:
    head = (f"POST {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: WISPR-Lab/1.0\r\n"
            f"Content-Type: {content_type}\r\nContent-Length: {len(body)}\r\n\r\n")
    return head.encode("ascii") + body


def _http_get(host: str, path: str) -> bytes:
    return f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nAccept: */*\r\n\r\n".encode("ascii")


def _http_ok(body: bytes, content_type: str = "application/json") -> bytes:
    return f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def generate_http_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    level = HTTP_LEVELS[spec.difficulty]
    server, host = _private_ip("10.20.0"), "intranet.local"
    clients = [_private_ip("192.168.10") for _ in range(4)]
    flag, split_at = spec.flag, None
    if level["style"] == "json":
        request = _http_post(host, "/api/reportes", f'{{"mensaje": "{flag}"}}'.encode(), "application/json")
    elif level["style"] == "urlencoded":
        request = _http_post(host, "/api/reportes", f"usuario=lab&mensaje={quote(flag, safe='')}".encode(), "application/x-www-form-urlencoded")
    else:
        encoded = base64.b64encode(flag.encode())
        request = _http_post(host, "/api/reportes", b'{"tipo": "respaldo", "dato": "' + encoded + b'"}', "application/json")
        # El corte cae DENTRO del base64: ningún paquete suelto lo trae entero.
        split_at = request.index(encoded) + _rng.randint(4, len(encoded) - 4)
    sessions = [_http_session(_rng.choice(clients), server, request, _http_ok(b'{"ok": true}'), split_at)]

    for _ in range(_rng.randint(*level["noise"])):
        client = _rng.choice(clients)
        if level["style"] == "split_base64" and _rng.random() < 0.3:
            decoy = base64.b64encode(_rng.choice(_HTTP_DECOYS).encode()).decode()
            request = _http_post(host, "/api/reportes", f'{{"tipo": "respaldo", "dato": "{decoy}"}}'.encode(), "application/json")
            response = _http_ok(b'{"ok": true}')
        elif _rng.random() < 0.3:
            request = _http_post(host, "/api/buscar", f"q={quote(_rng.choice(_HTTP_DECOYS))}".encode(), "application/x-www-form-urlencoded")
            response = _http_ok(b'{"resultados": 0}')
        else:
            request = _http_get(host, _rng.choice(_HTTP_PAGES))
            response = _http_ok(b"<html><body>WISPR intranet</body></html>", "text/html")
        sessions.append(_http_session(client, server, request, response))
    _rng.shuffle(sessions)

    packets, clock = [], 1_760_000_000.0 + _rng.randint(0, 86_400)
    for session in sessions:
        for packet in session:
            clock += _rng.uniform(0.0005, 0.04)
            packet.time = clock
            packets.append(Ether(src=_random_mac(), dst=_random_mac()) / packet)
        clock += _rng.uniform(0.1, 2.0)

    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wrpcap(str(output_path), packets)
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# stego_png — esteganografía en una imagen PNG (22 oct)
# ─────────────────────────────────────────────────────────────────────────
# La imagen la arma este módulo (PNG RGB sin compresión de filtro, con zlib de
# la biblioteca estándar): no hace falta Pillow en el backend.
#   easy   -> la flag en un metadato de texto (chunk tEXt "Comment"):
#             exiftool o strings la muestran.
#   medium -> el metadato es un señuelo y la flag va en base64 DESPUÉS del
#             final del PNG (IEND). Buscar "WISPR{" ya no la encuentra.
#   hard   -> la flag escondida en el bit menos significativo (LSB) del canal
#             rojo, píxel por píxel de izquierda a derecha y de arriba abajo,
#             8 bits por carácter (el más significativo primero) y un byte 0
#             al final. Los datos tras el IEND son un señuelo (base64 que no es
#             la flag): el método de medium da otra cosa.
STEGO_LEVELS = {
    "easy": {"where": "metadata"},
    "medium": {"where": "trailer"},
    "hard": {"where": "lsb"},
}
_STEGO_SIZE = 96  # 96x96 = 9216 píxeles: sobra para una flag de 180 caracteres (1448 bits)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png_pixels(size: int) -> bytearray:
    """Un degradado con algo de ruido: parece una foto, no un archivo vacío."""
    seed_r, seed_g, seed_b = (_rng.randint(0, 255) for _ in range(3))
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            noise = _rng.randint(-12, 12)
            pixels += bytes(((seed_r + x * 2 + noise) % 256, (seed_g + y * 2 + noise) % 256, (seed_b + (x + y) + noise) % 256))
    return pixels


def _embed_lsb(pixels: bytearray, message: bytes) -> None:
    bits = [(byte >> (7 - i)) & 1 for byte in message + b"\x00" for i in range(8)]
    for index, bit in enumerate(bits):
        red = index * 3
        pixels[red] = (pixels[red] & 0xFE) | bit


def generate_stego_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    where = STEGO_LEVELS[spec.difficulty]["where"]
    size = _STEGO_SIZE
    pixels = _png_pixels(size)
    comment, trailer = "Foto del laboratorio de redes", b""
    if where == "metadata":
        comment = spec.flag
    elif where == "trailer":
        trailer = base64.b64encode(spec.flag.encode()) + b"\n"
    else:
        _embed_lsb(pixels, spec.flag.encode())
        trailer = base64.b64encode(_rng.choice(_HTTP_DECOYS).encode()) + b"\n"

    rows = b"".join(b"\x00" + bytes(pixels[y * size * 3:(y + 1) * size * 3]) for y in range(size))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + _png_chunk(b"tEXt", b"Software\x00WISPR Camera 2.1")
        + _png_chunk(b"tEXt", b"Comment\x00" + comment.encode("latin-1"))
        + _png_chunk(b"IDAT", zlib.compress(rows, 9))
        + _png_chunk(b"IEND", b"")
        + trailer
    )
    output_path = output_path or _default_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png)
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
    "caesar_vigenere": generate_caesar_challenge,
    "encoding_layers": generate_encoding_challenge,
    "http_plaintext_pcap": generate_http_challenge,
    "stego_png": generate_stego_challenge,
}


def materialize_challenge(spec: ChallengeSpec, output_path: Path | None = None) -> Path:
    """
    Punto de entrada del generador determinista: recibe un ChallengeSpec ya
    validado por Pydantic y devuelve la ruta del archivo real generado.
    Sin `output_path`, escribe en challenges/generated/<id>.<ext>.
    """
    generator = TECHNIQUE_REGISTRY[spec.technique]
    return generator(spec, output_path)
