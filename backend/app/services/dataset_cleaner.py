"""
Limpieza del dataset de retos del equipo (`challenges.json`, 581 retos) —
guía del ingeniero, fase 1.

Desde backend/:
    python -m app.services.dataset_cleaner ../challenges/dataset/challenges_original.json ../challenges/dataset/challenges_limpio.json

Qué hace (todo automático y repetible; el original no se toca):
  1. Corrige los datos sucios conocidos (campo `!difficulty` de web-wifi-66,
     título "etadata de Imagen" de reverse-wifi-33).
  2. FLAG{...} -> WISPR{...}.
  3. Separa `technique` (texto libre, 567 valores distintos) en `technique`
     (un valor del registro, o "" si no hay generador) y `technique_notes`.
  4. Marca el lote: "manual" (9 sep, la base buena) o "ia" (2 oct).
  5. Del lote "ia" descarta los retos que no cumplen el criterio de la guía:
     la solución nombra herramientas y pasos concretos, y el reto dice qué
     archivo o recurso recibe el jugador.
  6. Elimina flags duplicadas (se queda la primera, priorizando el lote
     manual) y renombra títulos repetidos (II, III...).
  7. Valida cada reto con DatasetChallenge y deja un reporte.

Lo automático no reemplaza la revisión humana que pide la guía: el reporte
lista lo que conviene mirar a mano (títulos renombrados, flags que revelan el
tema). Desde el 13 oct la flag de los retos jugables la genera el backend,
así que la flag del dataset solo importa como dato de entrenamiento.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from app.schemas.challenge import DatasetChallenge

MANUAL_DATE = "2026-09-09"
TITLE_FIXES = {"etadata de Imagen": "Metadata de Imagen"}

# Herramientas concretas: si la solución nombra alguna, no es "genérica".
TOOLS = (
    "wireshark", "tshark", "tcpdump", "scapy", "aircrack", "airodump", "aireplay", "hashcat", "john",
    "hydra", "nmap", "burp", "zap", "curl", "sqlmap", "gobuster", "dirb", "nikto", "python", "cyberchef",
    "base64", "xxd", "hexdump", "strings", "binwalk", "exiftool", "steghide", "stegsolve", "zsteg",
    "foremost", "volatility", "openssl", "ghidra", "radare", "gdb", "objdump", "file ", "grep", "jwt",
    "devtools", "consola del navegador", "dig", "nslookup", "hashid", "sha256", "md5", "rot13", "xor",
    "frecuencia", "fuerza bruta", "diccionario", "wordlist", "rockyou", "javascript", "tabla arco",
    "factoriz", "lsb", "metadatos", "exif", "hexadecimal",
)
# Frases que la guía encontró en 88 soluciones del lote de IA ("utiliza herramientas" sin decir cuáles),
# más las muletillas que el lote de IA repite sin decir nada concreto.
GENERIC = re.compile(
    r"\b(utiliza|utilizar|usa|usar|emplea|emplear)\s+(las\s+)?herramientas\b(?!\s+como)"
    r"|patrones o anomal[ií]as|analizar su contenido",
    re.IGNORECASE,
)
# El reto dice qué recibe el jugador.
ARTIFACT = re.compile(
    r"archivo|captura|pcap|imagen|foto|binario|ejecutable|firmware|apk|\blog\b|registro|volcado|dump|"
    r"portal|p[aá]gina|panel|formulario|\burl\b|endpoint|api|certificado|documento|audio|video|zip|"
    r"c[oó]digo fuente|script|base de datos|cookie|token|paquetes|tr[aá]fico|beacon|ssid|correo",
    re.IGNORECASE,
)
MIN_SOLUTION = 90   # mediana del lote de IA: 96 caracteres; del manual: 146
MIN_STEPS = 2       # o nombrar una herramienta: "buscar el hash en una tabla arcoíris de MD5" es concreto


def _technique(notes: str) -> str:
    text = notes.lower()
    if "iv" in text and ("wep" in text or "keystream" in text):
        return "iv_reuse_wep"
    if "xor" in text and ("byte" in text or "un solo" in text):
        return "xor_singlebyte"
    return ""


def _steps(solution: str) -> int:
    return len([p for p in re.split(r"[,;.]|\by luego\b|\bluego\b|\bdespu[eé]s\b|\d\)", solution) if p.strip()])


def rejection_reason(entry: dict) -> str | None:
    """Por qué un reto del lote de IA no pasa el criterio de la guía (None si pasa)."""
    solution = entry["solution"]
    lower = solution.lower()
    names_tool = any(tool in lower for tool in TOOLS)
    if GENERIC.search(solution) and not names_tool:
        return "solución genérica (sin herramientas ni pasos concretos)"
    if len(solution) < MIN_SOLUTION and not names_tool:
        return "solución corta sin herramientas"
    if _steps(solution) < MIN_STEPS and not names_tool:
        return "solución sin pasos concretos"
    if not ARTIFACT.search(entry["description"] + " " + solution):
        return "no dice qué recibe el jugador"
    return None


def _roman(n: int) -> str:
    return {2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}.get(n, str(n))


def clean(raw: dict) -> tuple[list[dict], dict]:
    entries = sorted(raw["challenges"], key=lambda e: (not e["created_at"].startswith(MANUAL_DATE), e["created_at"], e["id"]))
    report = {"total": len(entries), "rechazados": {}, "flags_duplicadas": [], "titulos_renombrados": {},
              "flags_que_revelan_el_tema": 0}
    seen_flags: set[str] = set()
    title_count: Counter = Counter()
    kept = []
    for entry in entries:
        entry = {k: v for k, v in entry.items() if not k.startswith("!")}
        batch = "manual" if entry["created_at"].startswith(MANUAL_DATE) else "ia"
        if batch == "ia":
            reason = rejection_reason(entry)
            if reason:
                report["rechazados"].setdefault(reason, []).append(entry["id"])
                continue

        flag = re.sub(r"^FLAG\{", "WISPR{", entry["flag"].strip())
        if flag in seen_flags:
            report["flags_duplicadas"].append(entry["id"])
            continue
        seen_flags.add(flag)

        title = TITLE_FIXES.get(entry["title"].strip(), entry["title"].strip())
        title_count[title.casefold()] += 1
        if title_count[title.casefold()] > 1:
            new_title = f"{title} {_roman(title_count[title.casefold()])}"
            report["titulos_renombrados"][entry["id"]] = new_title
            title = new_title

        notes = entry["technique"].strip()
        challenge = DatasetChallenge(
            id=entry["id"], batch=batch, difficulty=entry["difficulty"], category=entry["category"],
            title=title, description=entry["description"].strip(), technique=_technique(notes),
            technique_notes=notes, flag=flag, hint=entry["hint"].strip(), solution=entry["solution"].strip(),
            created_at=entry["created_at"],
        )
        # Flag "que se adivina": su contenido es el tema en palabras (vigenere_is_weak).
        if re.fullmatch(r"WISPR\{[a-z]+(_[a-z]+){2,}\}", flag):
            report["flags_que_revelan_el_tema"] += 1
        kept.append(challenge.model_dump())

    report["conservados"] = len(kept)
    report["por_lote"] = dict(Counter(c["batch"] for c in kept))
    report["por_categoria"] = dict(Counter(c["category"] for c in kept))
    report["con_tecnica_del_registro"] = sum(1 for c in kept if c["technique"])
    return kept, report


def main(argv: list[str]) -> None:
    source, target = Path(argv[1]), Path(argv[2])
    kept, report = clean(json.loads(source.read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"report": report, "challenges": kept}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rejected = sum(len(ids) for ids in report["rechazados"].values())
    print(f"{report['conservados']} de {report['total']} conservados ({report['por_lote']}); "
          f"{rejected} rechazados del lote de IA, {len(report['flags_duplicadas'])} por flag duplicada, "
          f"{len(report['titulos_renombrados'])} títulos renombrados.")
    for reason, ids in report["rechazados"].items():
        print(f"  - {reason}: {len(ids)}")


if __name__ == "__main__":
    main(sys.argv)
