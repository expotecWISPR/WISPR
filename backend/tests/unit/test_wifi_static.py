"""
Verifica los archivos estáticos de los retos Wi-Fi (challenges/static/,
generados con challenges/static/generar_wifi.js): cada .pcap se resuelve con
Python/Scapy — sin usar el código Node que los generó — y el resultado tiene
que ser la flag de challenges/catalog/catalog.json. Si alguien regenera los
archivos o edita el catálogo a mano y quedan desalineados, esto falla.

Se resuelven como lo haría un estudiante: deauth = el BSSID que más deauth
recibe; WPA = diccionario contra el MIC del handshake (PBKDF2 + PRF-512);
PMKID = diccionario contra el PMKID del M1.
"""

import hashlib
import hmac
import json
from collections import Counter

import pytest
from scapy.all import EAPOL, Dot11, Dot11Beacon, Dot11Deauth, Dot11Elt, rdpcap

from app.services.challenges import CATALOG_FILE, STATIC_DIR

CATALOG = [c for c in json.loads(CATALOG_FILE.read_text(encoding="utf-8"))["challenges"] if c.get("kind")]


def _mac(value: str) -> bytes:
    return bytes.fromhex(value.replace(":", ""))


def _prf512(pmk: bytes, label: bytes, data: bytes) -> bytes:
    return b"".join(hmac.new(pmk, label + b"\x00" + data + bytes([i]), hashlib.sha1).digest() for i in range(4))[:64]


def _crack(challenge: dict) -> str | None:
    folder = STATIC_DIR / challenge["id"]
    packets = rdpcap(str(folder / challenge["files"][0]["name"]))
    if challenge["kind"] == "deauth":
        victims = Counter(p[Dot11].addr3 for p in packets if p.haslayer(Dot11Deauth))
        return "WISPR{deauth_%s}" % victims.most_common(1)[0][0].replace(":", "")

    words = (folder / "wordlist.txt").read_text(encoding="utf-8").split()
    ssid = next(p[Dot11Elt].info for p in packets if p.haslayer(Dot11Beacon))
    eapols = [p for p in packets if p.haslayer(EAPOL)]
    frames = [bytes(p[EAPOL]) for p in eapols]
    ap, sta = _mac(eapols[0][Dot11].addr2), _mac(eapols[0][Dot11].addr1)
    for word in words:
        pmk = hashlib.pbkdf2_hmac("sha1", word.encode(), ssid, 4096, 32)
        if challenge["kind"] == "pmkid":
            if hmac.new(pmk, b"PMK Name" + ap + sta, hashlib.sha1).digest()[:16] == frames[0][-16:]:
                return "WISPR{%s}" % word
        else:
            m1, m2 = frames[0], frames[1]
            anonce, snonce, mic = m1[17:49], m2[17:49], m2[81:97]
            ptk = _prf512(pmk, b"Pairwise key expansion",
                          min(ap, sta) + max(ap, sta) + min(anonce, snonce) + max(anonce, snonce))
            if hmac.new(ptk[:16], m2[:81] + b"\x00" * 16 + m2[97:], hashlib.sha1).digest()[:16] == mic:
                return "WISPR{%s}" % word
    return None


def test_hay_8_retos_wifi_con_archivos():
    assert len(CATALOG) == 8
    for challenge in CATALOG:
        for file in challenge["files"]:
            assert (STATIC_DIR / challenge["id"] / file["name"]).is_file()


@pytest.mark.parametrize("challenge", CATALOG, ids=lambda c: c["id"])
def test_el_archivo_se_resuelve_a_la_flag_del_catalogo(challenge):
    assert _crack(challenge) == challenge["flag"]
