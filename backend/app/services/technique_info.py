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
    # --- Técnicas agregadas el 22 oct ---------------------------------------
    "caesar_vigenere": {
        "name": "Cifrado César y Vigenère",
        "spec_category": "crypto",
        "label": "Criptografía clásica",
        "flag_prefix": "clasico",
        "tools": ["python3", "tr"],
        "levels": {
            "easy": {
                "ext": "txt",
                "file_desc": "Mensaje cifrado con ROT13",
                "objective": "El mensaje está cifrado con ROT13: cada letra se desplazó 13 posiciones en el alfabeto. Los números, «_» y las llaves no cambian.",
                "hint": "ROT13 se deshace aplicándolo otra vez: tr 'A-Za-z' 'N-ZA-Mn-za-m' < archivo.",
                "solution": "1) Leer el archivo. 2) Desplazar cada letra 13 posiciones (tr 'A-Za-z' 'N-ZA-Mn-za-m'). 3) El resultado es la flag.",
            },
            "medium": {
                "ext": "txt",
                "file_desc": "Mensaje cifrado con César",
                "objective": "El mensaje está cifrado con César con un desplazamiento desconocido (no es 13). Solo hay 25 desplazamientos posibles: pruébalos y quédate con el que produce un texto que empieza con WISPR{.",
                "hint": "Un bucle de 1 a 25 en Python alcanza; también puedes calcular el desplazamiento comparando la primera letra con la W de WISPR.",
                "solution": "1) Para cada desplazamiento s de 1 a 25, restar s a cada letra (mod 26). 2) El único que empieza con 'WISPR{' es la flag. Atajo: s = (letra cifrada − 'W') mod 26.",
            },
            "hard": {
                "ext": "txt",
                "file_desc": "Mensaje cifrado con Vigenère",
                "objective": "El mensaje está cifrado con Vigenère: una llave de 3 a 5 letras que se repite (solo avanza con las letras). Probar desplazamientos de César ya no sirve. Sabes que las 5 primeras letras son WISPR: con eso recuperas la llave.",
                "hint": "Cada letra de la llave = (letra cifrada − letra conocida) mod 26. Las 5 letras de WISPR te dan hasta 5 letras de llave: prueba largos de 3 a 5.",
                "solution": "1) k[i] = (cifrado[i] − 'WISPR'[i]) mod 26 para las 5 primeras letras. 2) Para cada largo L de 3 a 5, repetir k[:L] sobre todas las letras (sin contar dígitos ni símbolos) y restar. 3) El largo correcto da 'WISPR{clasico_…}' legible.",
            },
        },
    },
    "encoding_layers": {
        "name": "Capas de codificación (base64, hex, base32)",
        "spec_category": "misc",
        "label": "Codificación",
        "flag_prefix": "enc",
        "tools": ["base64", "base32", "xxd", "python3"],
        "levels": {
            "easy": {
                "ext": "txt",
                "file_desc": "Texto codificado",
                "objective": "El texto está codificado en base64: no es un cifrado, no hay llave. Decodifícalo para recuperar la flag.",
                "hint": "base64 usa letras, números, + y /, y a veces termina en =. Prueba: base64 -d archivo.",
                "solution": "1) base64 -d archivo. 2) El resultado es la flag.",
            },
            "medium": {
                "ext": "txt",
                "file_desc": "Texto con dos capas de codificación",
                "objective": "El texto tiene DOS capas de codificación distintas, elegidas entre base64, hex y base32. Reconoce cada capa por sus caracteres, decodifícala y repite hasta llegar a WISPR{.",
                "hint": "hex: solo 0-9 y a-f. base32: solo mayúsculas, 2-7 y relleno =. base64: el resto (mayúsculas, minúsculas, +, /).",
                "solution": "1) Mirar el alfabeto: hex → xxd -r -p; base32 → base32 -d; base64 → base64 -d. 2) Repetir con el resultado. 3) Tras 2 capas aparece la flag.",
            },
            "hard": {
                "ext": "txt",
                "file_desc": "Texto con varias capas de codificación",
                "objective": "El texto tiene 3 o 4 capas de codificación (base64, hex y base32, en cualquier orden y nunca la misma dos veces seguidas). Reconoce y decodifica capa por capa hasta llegar a WISPR{.",
                "hint": "Revisa siempre en este orden: ¿solo 0-9 a-f? → hex. ¿Solo A-Z, 2-7 y =? → base32. Si no, base64. Un script pequeño en Python lo automatiza.",
                "solution": "1) En un bucle: si el texto es solo [0-9a-f] → hex; si es solo [A-Z2-7=] → base32; si no → base64. 2) Decodificar y repetir. 3) Parar cuando empiece con 'WISPR{'.",
            },
        },
    },
    "http_plaintext_pcap": {
        "name": "Datos en HTTP sin cifrar dentro de una captura",
        "spec_category": "network",
        "label": "Análisis de tráfico",
        "flag_prefix": "http",
        "tools": ["wireshark", "tshark", "python3"],
        "levels": {
            "easy": {
                "ext": "pcap",
                "file_desc": "Captura con una petición HTTP",
                "objective": "La captura tiene una petición HTTP POST sin cifrar (puerto 80). Como HTTP no usa TLS, el cuerpo de la petición se lee completo: ahí va la flag.",
                "hint": "En Wireshark, filtra por http y abre el POST (sección «JavaScript Object Notation»). En tshark: -Y 'http.request.method == \"POST\"' -T fields -e json.value.string.",
                "solution": "1) Filtrar 'http.request.method == \"POST\"'. 2) Leer el cuerpo JSON (en tshark, -e json.value.string): el campo «mensaje» es la flag.",
            },
            "medium": {
                "ext": "pcap",
                "file_desc": "Captura con tráfico HTTP de varios equipos",
                "objective": "Entre muchas sesiones HTTP (páginas, búsquedas) hay un POST a /api/reportes con la flag en un formulario. El formulario va codificado en URL (las llaves viajan como %7B y %7D): buscar «WISPR{» en el archivo con strings no la encuentra. Hay que filtrar la petición correcta y leer sus campos.",
                "hint": "Filtra con http.request.uri contains \"reportes\". Wireshark (sección «HTML Form URL Encoded») y tshark (-e urlencoded-form.value) ya decodifican el %7B a «{».",
                "solution": "1) Filtrar 'http.request.uri contains \"reportes\"'. 2) Leer los campos del formulario (tshark -T fields -e urlencoded-form.key -e urlencoded-form.value). 3) El campo «mensaje» es la flag (a mano: %7B = «{», %7D = «}»).",
            },
            "hard": {
                "ext": "pcap",
                "file_desc": "Captura HTTP con varios reportes",
                "objective": "Hay varios POST a /api/reportes con un campo «dato» en base64, pero solo uno es la flag; los demás son señuelos. La petición con la flag viaja partida en dos segmentos TCP: para leerla completa hay que reensamblar el flujo.",
                "hint": "Wireshark y tshark reensamblan el flujo TCP solos (o usa «Follow TCP Stream»). Lista cada «dato» con -Y 'http.request.uri contains \"reportes\"' -T fields -e json.value.string y decodifícalos con base64 -d: solo uno empieza con WISPR{.",
                "solution": "1) Filtrar los POST a /api/reportes (el que lleva la flag viene en 2 segmentos TCP; Wireshark lo reensambla). 2) Listar los «dato» (tshark -T fields -e json.value.string). 3) Decodificar cada uno con base64 -d. 4) El que empieza con 'WISPR{' es la flag.",
            },
        },
    },
    "stego_png": {
        "name": "Esteganografía en imágenes PNG",
        "spec_category": "stego",
        "label": "Esteganografía",
        "flag_prefix": "stego",
        "tools": ["exiftool", "strings", "binwalk", "xxd", "python3"],
        "levels": {
            "easy": {
                "ext": "png",
                "file_desc": "Imagen PNG",
                "objective": "La imagen guarda la flag en sus metadatos: un PNG puede llevar textos (chunks tEXt) que no se ven al abrirla.",
                "hint": "exiftool imagen.png muestra los metadatos; strings imagen.png también sirve.",
                "solution": "1) exiftool imagen.png (o strings). 2) El campo «Comment» es la flag.",
            },
            "medium": {
                "ext": "png",
                "file_desc": "Imagen PNG",
                "objective": "Los metadatos son un señuelo. La flag está escondida DESPUÉS del final del PNG (el bloque IEND), codificada en base64: el visor de imágenes ignora todo lo que hay después.",
                "hint": "Busca qué hay tras «IEND» con xxd o strings; lo que quede al final es base64.",
                "solution": "1) xxd imagen.png | tail, o strings: tras 'IEND' hay una línea en base64. 2) base64 -d de esa línea da la flag.",
            },
            "hard": {
                "ext": "png",
                "file_desc": "Imagen PNG",
                "objective": "La flag está en los píxeles: en el bit menos significativo (LSB) del canal ROJO, píxel por píxel de izquierda a derecha y de arriba abajo, 8 bits por carácter (el más significativo primero), terminada en un byte 0. Lo que hay tras el IEND es un señuelo.",
                "hint": "Con Python y PIL: Image.open(...).convert('RGB'), recorre getdata() y junta (r & 1) de cada píxel en grupos de 8.",
                "solution": "1) Abrir la imagen con PIL. 2) Para cada píxel en orden, tomar r & 1. 3) Agrupar los bits de a 8 (MSB primero) y convertir a bytes. 4) Cortar en el primer byte 0: es la flag.",
            },
        },
    },
}


def technique_level(technique: str, difficulty: str) -> dict:
    """Textos de una técnica en un nivel (`difficulty` en easy/medium/hard)."""
    return TECHNIQUES[technique]["levels"][difficulty]
