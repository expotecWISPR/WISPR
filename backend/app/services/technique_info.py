"""
Textos técnicos de cada técnica y nivel: lo que el jugador TIENE que saber
para resolver el reto (objetivo, pista técnica, archivo) y la solución para
el docente.

Los escribe el equipo, no la IA (guía del ingeniero, 12 oct: "la dificultad
la decide el código, no la IA"). La IA solo escribe la historia (título,
descripción y una pista narrativa, ver ai_advisor.py); si se equivoca o
inventa algo, estos textos siguen diciendo la verdad sobre el archivo, así
que el reto nunca queda imposible por culpa de la IA. También son el
"resumen técnico" que se le pasa a la IA para que su pista tenga sentido.

Los parámetros que hacen difícil cada nivel (largo de la llave, cantidad de
paquetes) viven en challenge_generator.py; estos textos los describen.
"""

# ARP conocido del reto WEP. Fijo a propósito: ES el texto conocido que el
# jugador reconstruye, y está documentado en el objetivo. Lo que sí cambia en
# cada archivo (IV, MACs, llave) está en challenge_generator.py.
KNOWN_ARP_SRC_IP = "192.168.1.100"
KNOWN_ARP_DST_IP = "192.168.1.1"

# Vocabulario de dificultad del frontend (catálogo) -> el de ChallengeSpec.
# Las técnicas llegan hasta "hard": un reto "Expert" se genera como hard.
LEVEL_TO_SPEC = {"Foundation": "easy", "Medium": "medium", "Hard": "hard", "Expert": "hard"}

TECHNIQUES = {
    "xor_singlebyte": {
        "name": "XOR con llave repetida",  # para el prompt de la IA
        "spec_category": "crypto",   # categoría de ChallengeSpec
        "label": "Criptografía",     # categoría que muestra el frontend
        "flag_prefix": "xor",
        "tools": ["python3", "xxd"],
        "levels": {
            "easy": {
                "ext": "bin",
                "file_desc": "Archivo cifrado con XOR",
                "objective": "El archivo está cifrado con XOR usando una llave de 1 byte. Prueba las 256 llaves posibles y quédate con la que produce texto que empieza con WISPR{.",
                "hint": "Con 1 byte solo hay 256 llaves: un bucle de 0 a 255 en Python alcanza.",
                "solution": "1) Leer el archivo. 2) Para cada llave k de 0 a 255: bytes(b ^ k for b in datos). 3) La única salida que empieza con 'WISPR{' y termina en '}' es la flag.",
            },
            "medium": {
                "ext": "bin",
                "file_desc": "Archivo cifrado con XOR de llave repetida",
                "objective": "El archivo está cifrado con XOR usando una llave de 2 a 4 bytes que se repite. Probar 256 llaves de 1 byte ya no sirve: usa que sabes cómo empieza el texto (WISPR{).",
                "hint": "Si sabes el texto original de los primeros bytes, cifrado XOR conocido = llave. Prueba largos de llave de 2 a 4.",
                "solution": "1) Texto conocido: los 6 primeros bytes son 'WISPR{'. 2) llave[i] = cifrado[i] XOR conocido[i]. 3) Para cada largo L de 2 a 4, repetir llave[:L] sobre todo el archivo. 4) El largo correcto da un texto legible que termina en '}'.",
            },
            "hard": {
                "ext": "txt",
                "file_desc": "Texto en base64 de un archivo cifrado con XOR",
                "objective": "El contenido está en base64 y, debajo, cifrado con XOR usando una llave de 5 o 6 bytes que se repite. Decodifica primero y después recupera la llave con el texto conocido.",
                "hint": "Primero base64 -d. Después, los 6 primeros bytes del texto original son WISPR{: alcanzan para una llave de hasta 6 bytes.",
                "solution": "1) base64 -d al archivo. 2) llave[i] = cifrado[i] XOR 'WISPR{'[i] para i < 6. 3) Probar largos 5 y 6 repitiendo la llave sobre todo el contenido. 4) El largo correcto da la flag completa.",
            },
        },
    },
    "iv_reuse_wep": {
        "name": "Reutilización de IV en WEP (RC4)",
        "spec_category": "network",
        "label": "WEP",
        "flag_prefix": "wep",
        "tools": ["wireshark", "tshark", "scapy", "python3"],
        "levels": {
            "easy": {
                "ext": "pcap",
                "file_desc": "Captura 802.11 con 2 tramas WEP",
                "objective": (
                    "La captura tiene 2 tramas WEP con el MISMO IV. La primera es un ARP request: cabecera "
                    "LLC/SNAP AA AA 03 00 00 00 08 06 + ARP (op=1) desde la MAC de origen de la trama, IP "
                    f"{KNOWN_ARP_SRC_IP}, preguntando por {KNOWN_ARP_DST_IP}. keystream = cifrado1 XOR conocido; "
                    "flag = cifrado2 XOR keystream (sin los 8 bytes de SNAP)."
                ),
                "hint": "Mismo IV = mismo keystream de RC4. Reconstruye el ARP con scapy y haz XOR.",
                "solution": "1) rdpcap y tomar wepdata de las 2 tramas. 2) Conocido = SNAP + bytes(ARP(op=1, hwsrc=trama1.addr2, psrc='192.168.1.100', pdst='192.168.1.1')). 3) keystream = wepdata1 XOR conocido. 4) wepdata2 XOR keystream; quitar los 8 bytes de SNAP: es la flag.",
            },
            "medium": {
                "ext": "pcap",
                "file_desc": "Captura 802.11 WEP con tráfico de ruido",
                "objective": (
                    "Entre 20 y 50 tramas WEP, solo 2 comparten IV. De ese par, la primera es un ARP request: "
                    "LLC/SNAP AA AA 03 00 00 00 08 06 + ARP (op=1) desde la MAC de origen de la trama, IP "
                    f"{KNOWN_ARP_SRC_IP}, preguntando por {KNOWN_ARP_DST_IP}. La segunda lleva la flag."
                ),
                "hint": "Agrupa las tramas por IV (wep.iv en Wireshark/tshark): solo un IV aparece dos veces.",
                "solution": "1) Agrupar las tramas por IV y quedarse con el que aparece 2 veces. 2) La primera del par es el ARP conocido (SNAP + ARP desde addr2, 192.168.1.100 -> 192.168.1.1). 3) keystream = wepdata1 XOR conocido. 4) wepdata2 XOR keystream sin los 8 bytes de SNAP = flag.",
            },
            "hard": {
                "ext": "pcap",
                "file_desc": "Captura 802.11 WEP grande",
                "objective": (
                    "Cientos de tramas WEP con IVs distintos, salvo un par que repite IV. Una de las dos es un ARP "
                    f"request con su cabecera LLC/SNAP (op=1, IP {KNOWN_ARP_SRC_IP} preguntando por "
                    f"{KNOWN_ARP_DST_IP}, MAC de origen = la de SU trama). No te decimos cuál es ni en qué orden aparecen."
                ),
                "hint": "Un ARP request con SNAP mide exactamente 36 bytes: el largo del wepdata delata cuál es, y su MAC de origen no es la de la otra trama.",
                "solution": "1) Buscar el único IV repetido entre cientos de tramas. 2) Identificar el ARP por su largo (36 bytes): lo envía el AP y va segundo. 3) Conocido = SNAP + ARP con hwsrc = addr2 de ESA trama (192.168.1.100 -> 192.168.1.1). 4) keystream = wepdata_arp XOR conocido; wepdata_flag XOR keystream sin SNAP = flag. Usar la MAC de la otra trama da 6 bytes de basura en la flag.",
            },
        },
    },
}


def technique_level(technique: str, difficulty: str) -> dict:
    """Textos de una técnica en un nivel (`difficulty` en easy/medium/hard)."""
    return TECHNIQUES[technique]["levels"][difficulty]
