"""
Generador determinista de archivos de retos (materialización).

Este módulo es la segunda mitad del pipeline de generación de retos con IA
(ver docs/pipeline_ia_retos.md). Together AI solo propone un ChallengeSpec
ya validado por Pydantic — este archivo es el que realmente construye el
archivo/entorno del reto. La IA nunca ejecuta código ni genera bytes
directamente; solo elige una `technique` de este registro fijo.

Flujo:
    ChallengeSpec (ya validado por app/schemas/challenge.py)
        -> TECHNIQUE_REGISTRY[spec.technique]
        -> función generadora específica de esta técnica
        -> archivo real en challenges/generated/

TODO (fuera de este alcance, ver .claude/memory/reparto_tareas.md): subir
el archivo resultante a S3 en vez de dejarlo en disco local. Por ahora se
escribe en challenges/generated/, que ya está en .gitignore porque cada
archivo generado es único (tiene su propia flag) y no debe ir al repo.
"""

import os
from pathlib import Path

from scapy.layers.dot11 import Dot11, Dot11WEP, RadioTap
from scapy.layers.l2 import ARP
from scapy.utils import wrpcap

from app.schemas.challenge import ChallengeSpec

GENERATED_DIR = Path(__file__).resolve().parents[3] / "challenges" / "generated"


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

# IV fijo, reutilizado a propósito en ambos paquetes: esa reutilización es
# la vulnerabilidad que el estudiante tiene que explotar.
_REUSED_IV = b"\x00\x00\x01"

_AP_MAC = "aa:bb:cc:00:11:22"
_STA_MAC = "de:ad:be:ef:00:01"


def _build_known_plaintext(min_len: int) -> bytes:
    """
    Arma el paquete 1: SNAP header + un ARP request con campos fijos.
    Estos campos se documentan en la descripción/hint del reto, así que el
    estudiante puede reconstruir este plaintext exacto sin descifrar nada
    — es la mitad "conocida" del ataque. Se rellena con ceros al final
    para cubrir flags de cualquier longitud razonable.
    """
    known_arp = ARP(
        hwtype=1,
        ptype=0x0800,
        hwlen=6,
        plen=4,
        op=1,
        hwsrc="00:11:22:33:44:55",
        psrc="192.168.1.1",
        hwdst="00:00:00:00:00:00",
        pdst="192.168.1.254",
    )
    plaintext = _SNAP_HEADER_ARP + bytes(known_arp)
    if len(plaintext) < min_len:
        plaintext += b"\x00" * (min_len - len(plaintext))
    return plaintext


def generate_wep_reused_iv_pcap(spec: ChallengeSpec) -> Path:
    """
    Genera un .pcap con dos frames 802.11 WEP que reutilizan el mismo IV:

    - Paquete 1: plaintext conocido (SNAP header + ARP request estándar +
      relleno en ceros), documentado en la descripción/hint del reto.
    - Paquete 2: mismo SNAP header + la flag, cifrado con el MISMO IV.

    Como RC4(IV+key) produce el mismo keystream para ambos paquetes, el
    estudiante recupera la flag sin conocer la llave WEP:

        keystream   = ciphertext_1 XOR plaintext_1_conocido
        plaintext_2 = ciphertext_2 XOR keystream

    Nota de alcance: se omite el ICV (CRC32) real de WEP a propósito — no
    aporta nada a la vulnerabilidad enseñada (reutilización de IV) y solo
    agregaría complejidad sin valor pedagógico.
    """
    flag_plaintext = _SNAP_HEADER_ARP + spec.flag.encode("utf-8")
    known_plaintext = _build_known_plaintext(min_len=len(flag_plaintext))

    # Llave WEP secreta, generada por instancia de reto. El estudiante
    # nunca la necesita: el ataque explota la reutilización del IV, no
    # requiere recuperar la llave.
    wep_key = os.urandom(5)  # WEP-40
    rc4_key = _REUSED_IV + wep_key  # mismo IV para ambos paquetes -> mismo keystream

    ciphertext_1 = _rc4_crypt(rc4_key, known_plaintext)
    ciphertext_2 = _rc4_crypt(rc4_key, flag_plaintext)

    def _frame(wepdata: bytes) -> object:
        return (
            RadioTap()
            / Dot11(type=2, subtype=0, FCfield="protected", addr1=_AP_MAC, addr2=_STA_MAC, addr3=_AP_MAC)
            / Dot11WEP(iv=_REUSED_IV, keyid=0, wepdata=wepdata, icv=0)
        )

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_DIR / f"{spec.id}.pcap"
    wrpcap(str(output_path), [_frame(ciphertext_1), _frame(ciphertext_2)])
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# xor_singlebyte — reto de XOR de un solo byte (categoría crypto)
# ─────────────────────────────────────────────────────────────────────────
# La flag se cifra byte a byte contra UNA sola llave (un byte, 0-255)
# repetida. La vulnerabilidad es el espacio de llaves: con solo 256
# posibilidades, el estudiante puede probarlas todas (fuerza bruta) y
# quedarse con la que produce texto legible — no hace falta "romper" nada
# matemáticamente, es la lección de por qué una llave tan corta no sirve.
def generate_xor_challenge(spec: ChallengeSpec) -> Path:
    """
    Genera un archivo binario con la flag cifrada por XOR contra un solo
    byte aleatorio. El estudiante prueba las 256 llaves posibles (0-255) y
    se queda con la que produce un resultado legible (empieza con
    "WISPR{"), sin necesidad de conocer la llave de antemano:

        para cada llave en 0..255:
            texto = bytes(b ^ llave for b in ciphertext)
            si texto parece texto legible -> esa es la llave

    Escribe el archivo en GENERATED_DIR (challenges/generated/), igual que
    generate_wep_reused_iv_pcap.
    """
    key = os.urandom(1)[0]  # 0-255 — la llave que el estudiante debe encontrar por fuerza bruta
    plaintext = spec.flag.encode("utf-8")
    ciphertext = bytes(b ^ key for b in plaintext)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_DIR / f"{spec.id}.bin"
    output_path.write_bytes(ciphertext)
    return output_path


# ─────────────────────────────────────────────────────────────────────────
# Registro de técnicas — la pieza que le da seguridad al pipeline
# ─────────────────────────────────────────────────────────────────────────
# La IA solo puede elegir una `technique` que ya esté en este diccionario
# (reforzado también por el Literal en ChallengeSpec — ver ese archivo).
# Agregar una técnica nueva implica: 1) sumarla al Literal en
# app/schemas/challenge.py, 2) escribir y probar su función generadora
# acá, 3) registrarla en este diccionario.
TECHNIQUE_REGISTRY = {
    "iv_reuse_wep": generate_wep_reused_iv_pcap,
    "xor_singlebyte": generate_xor_challenge,
}


def materialize_challenge(spec: ChallengeSpec) -> Path:
    """
    Punto de entrada del generador determinista: recibe un ChallengeSpec ya
    validado por Pydantic y devuelve la ruta del archivo real generado.
    """
    generator = TECHNIQUE_REGISTRY[spec.technique]
    return generator(spec)
