# WISPR — Pipeline de Generación de Retos con IA

Este documento detalla cómo la IA participa en la creación de retos sin perder control ni
coherencia sobre lo que finalmente se le entrega al estudiante. Complementa las secciones
"Generación de retos" e "IA" de `CLAUDE.md`.

---

## Cambio del 13 oct 2026 — la IA solo escribe la historia

Aplicando la guía del ingeniero (`docs/Guía WISPR retos variados y dificultad adaptativa.pdf`).
Con 2 técnicas posibles, pedirle a la IA el reto entero hacía que solo variara el texto y terminara
repitiendo los ejemplos. El flujo actual es:

```
   El jugador resuelve un reto
              │
              ▼
   Motor adaptativo (difficulty.py) ── reglas: 1.º-2.º intento sube, 3-6 se mantiene, 6+ fallos baja
   decide TÉCNICA y NIVEL
              │
              ▼
   Together AI · Muse Glimmer 30B (ai_advisor.py; hasta el 23 oct, Llama 3.3 70B)
   recibe técnica + nivel + resumen técnico + escenario al azar + títulos ya vistos
   devuelve SOLO {title, description, hint}
              │  (texto no confiable)
              ▼
   ChallengeNarrative (Pydantic): largos, sin llaves, sin títulos repetidos
              │ inválido / timeout / sin key / límite   │ válido
              ▼                                          ▼
     historia de plantilla  ───────────────────►  Backend genera la FLAG (secrets)
                                                         │
                                                         ▼
                                     ChallengeSpec (Pydantic) — misma regla de siempre
                                                         │
                                                         ▼
                                     Generador (challenge_generator.py) con los
                                     parámetros del nivel → archivo PROPIO del jugador
                                                         │
                                                         ▼
                                     Reto nuevo, solo para ese jugador (owner_id)
                                     + su instancia (flag y archivo) en Supabase
```

El mismo flujo (desde la IA hacia abajo) se usa cuando **alguien pide un reto** eligiendo técnica,
dificultad y escenario (`POST /api/challenges/generate`, formulario en el frontend): el estudiante
recibe un reto de práctica solo para él (sin puntos) y el profesor/admin publica uno para todos los
estudiantes, cada uno con su archivo y su flag. La flag no se puede elegir: quien la elige ya sabe
la respuesta.

Lo que sigue de este documento describe el diseño original (26 ago). Sigue valiendo la regla de
seguridad (registro fijo de técnicas + validación antes de generar); lo que cambió es que la IA ya
no decide la flag, la técnica ni la dificultad.

---

## Estado de implementación (26 ago 2026, histórico)

Implementado y probado en ese momento en la rama `feature/retos-ia-persona2` (fusionada a `main` el
7 oct):

* ✅ `ChallengeSpec` (`app/schemas/challenge.py`) — schema completo, con el registro fijo de
  técnicas y validación de formato de flag.
* ✅ `TECHNIQUE_REGISTRY` (`app/services/challenge_generator.py`) — **ambas** técnicas del
  ejemplo de este documento están construidas: `iv_reuse_wep` y `xor_singlebyte`. Las dos se
  probaron simulando el ataque real (recuperar la flag sin conocer la llave de antemano), no
  solo verificando que el código corre sin error.
* ✅ Llamada a Together AI (`app/services/ai_advisor.py`) — probada con un cliente simulado.
  **(13 oct)** El respaldo ya existe (plantillas). Falta una `TOGETHER_API_KEY` válida para
  probarla contra la API real.
* ❌ Subida a S3 — los archivos generados quedan en `challenges/generated/` (local, en
  `.gitignore`), todavía no se suben a S3. Es tarea pendiente separada (ver checkpoint en
  `CLAUDE.md`).
* ❌ Fine-tuning con LoRA — se sigue usando el modelo base por inferencia estándar; el dataset
  de ~500 ejemplos lo sigue curando un compañero del equipo.

Tests: `backend/tests/unit/` (25 tests, `unittest` de la librería estándar). Correr con
`venv\Scripts\python.exe -m unittest discover -s tests/unit -v` desde `backend/`.

---

## Idea central

La IA **no genera el reto completo desde cero**. Genera una **especificación** (un JSON con
narrativa, flag, dificultad y la técnica a usar). Un motor determinista, ya construido por el
equipo, toma esa especificación y arma el archivo o entorno real. La IA nunca produce
directamente un `.pcap`, un binario, ni ningún archivo — eso no es una tarea que un modelo de
lenguaje haga bien de forma confiable, sin importar cuántos ejemplos de entrenamiento tenga.

---

## Diagrama del flujo

```
   Usuario/Admin solicita generar un reto
   (categoría + dificultad, elegidas de opciones fijas — no texto libre)
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  Together AI · Muse Glimmer 30B               │
   │  Genera un JSON con la especificación del reto│
   └───────────────────────┬───────────────────────┘
                            │  (texto, no confiable todavía)
                            ▼
   ┌─────────────────────────────────────────────┐
   │  Validación — Pydantic (ChallengeSpec)        │
   │  ¿Tiene todos los campos? ¿Tipos correctos?   │
   │  ¿La "technique" existe en el registro fijo?  │
   └───────────────┬───────────────────┬───────────┘
                    │ inválido           │ válido
                    ▼                    ▼
        Reintentar / usar reto   ┌─────────────────────────┐
        estático de respaldo     │  Registro de técnicas    │
                                  │  technique_id → función  │
                                  │  generadora (ej. Scapy)  │
                                  └────────────┬──────────────┘
                                               ▼
                                  ┌─────────────────────────┐
                                  │  Generador determinista  │
                                  │  (challenge_generator.py)│
                                  │  Construye el archivo/   │
                                  │  entorno real             │
                                  └────────────┬──────────────┘
                                               ▼
                          Archivo → S3   /   Contenedor Docker
                          Flag generada → guardada en Supabase
```

---

## El JSON de especificación

Formato acordado (basado en el ejemplo de trabajo del equipo):

```json
{
  "id": "crypto-wifi-01",
  "difficulty": "easy",
  "category": "network",
  "description": "Red WEP antigua con reutilización de IVs capturada.",
  "technique": "iv_reuse_wep",
  "flag": "WISPR{wep_died_for_a_reason}",
  "hint": "Busca IVs repetidos en el pcap.",
  "solution": "Extraer IVs duplicados, recuperar keystream, XOR contra ciphertext, decodificar flag embebida en el payload ARP."
}
```

Este JSON se valida con un modelo de Pydantic (`app/schemas/challenge.py`) antes de usarse:

```python
from pydantic import BaseModel
from typing import Literal

class ChallengeSpec(BaseModel):
    id: str
    difficulty: Literal["easy", "medium", "hard"]
    category: Literal["web", "crypto", "forensics", "network", "osint"]
    description: str
    technique: Literal["iv_reuse_wep", "xor_singlebyte"]  # se amplía según el registro real
    flag: str
    hint: str
    solution: str
```

Si el modelo devuelve un campo faltante, un tipo incorrecto, o un `technique` que no está en la
lista permitida, Pydantic rechaza el objeto automáticamente — nunca llega al generador.

---

## El registro de técnicas (la pieza que da seguridad)

La IA **elige** una técnica de una lista fija, no puede inventar una nueva. Cada técnica del
registro tiene una función Python ya construida y probada por el equipo que sabe generar un
archivo válido y resoluble para esa técnica específica:

```python
TECHNIQUE_REGISTRY = {
    "iv_reuse_wep": generate_wep_reused_iv_pcap,
    "xor_singlebyte": generate_xor_challenge,
    # se agregan más a medida que el equipo construye y prueba nuevos generadores
}
```

Esto es lo mismo que ya se decidió para evitar prompt injection en la interfaz (el usuario elige
de opciones, no escribe texto libre) — aplicado ahora también a lo que la IA puede pedirle al
sistema que construya.

---

## Por qué la flag es de bajo riesgo

La flag se genera **una sola vez**, en el momento de crear el reto, y se guarda en la base de
datos (Supabase). Validar la respuesta del estudiante después es solo comparar strings — nunca
hace falta volver a invocar a la IA para verificar una flag, lo cual evita problemas de
no-determinismo del modelo (un LLM puede dar respuestas distintas a la misma pregunta en
llamadas diferentes).

---

## Fine-tuning: LoRA, no fine-tuning completo

> **Estado real (23 oct):** no se usa ningún modelo ajustado. El intento de LoRA quedó trabado
> y la IA corre con `meta-models/Muse-Glimmer-30B` (modelo base + instrucciones, configurable
> con `TOGETHER_MODEL`). Llama 3.3 70B Instruct Turbo lo retiró Together el 23 oct. Lo que sigue
> es el plan original, conservado como referencia por si se retoma después de EXPOTEC.

* **Modelo base:** Llama 3.3 70B Instruct Turbo.
* **Método:** LoRA (Low-Rank Adaptation) — congela el modelo base y entrena solo una fracción
  pequeña de parámetros adicionales. Mucho más barato y rápido que reentrenar el modelo
  completo.
* **Dónde se entrena:** servicio de fine-tuning administrado de Together AI — el equipo no
  gestiona GPUs propias, solo sube el dataset.
* **Dataset:** ~500 ejemplos curados por el equipo, repartidos en varias categorías, en el
  formato JSON descrito arriba.
* **Por qué no fine-tuning completo:** se evaluó y se descartó antes en el proyecto — requiere
  GPUs dedicadas (ej. A100/H100) y días de entrenamiento, inviable con los recursos y tiempo
  del equipo. LoRA es la alternativa que sí es alcanzable.

**Antes de comprometer tiempo/presupuesto:** confirmar el costo publicado del fine-tuning con
LoRA en Together AI para un modelo de 70B, y validar que el formato del dataset (500 ejemplos)
sea suficiente para lograr resultados consistentes — si los resultados no son buenos con ese
tamaño, la alternativa de respaldo es usar los mismos ejemplos como *few-shot prompting* (sin
entrenar nada), que probablemente logre un resultado similar para esta tarea específica sin
costo de entrenamiento.

---

## Alcance para el MVP

No se implementa el pipeline completo para las 5 categorías antes de EXPOTEC. Se elige a
propósito:

* **Con pipeline completo (IA + generador):** crypto y network — ya hay ejemplos curados
  (ej. el reto WEP).
* **Retos estáticos, hechos a mano:** el resto de categorías (web, forensics, osint), hasta que
  haya tiempo de construir y probar sus generadores correspondientes.

Esto es intencional, no una limitación oculta — EXPOTEC evalúa lo que se logró construir y
demostrar, no la cobertura al 100% de todas las categorías.

---

## Nota de seguridad: si la IA llega a escribir código ejecutable

Si en algún punto el diseño evoluciona para que la IA genere directamente *código* (por ejemplo,
un script de Scapy) en vez de solo un JSON de parámetros, ese código nunca debe ejecutarse
directamente en el servidor. Debe correr en el mismo entorno aislado de Docker que ya está
planeado para los retos de los estudiantes (namespaces, seccomp, AppArmor, límites de
recursos) — no es infraestructura nueva, es extender el sandbox que ya existe también a "código
generado por la IA", no solo a "comandos del estudiante".

---

## Próximos pasos de implementación

1. Definir el `ChallengeSpec` real en `app/schemas/challenge.py`.
2. Construir el registro de técnicas y al menos 2 funciones generadoras (ej. `iv_reuse_wep`)
   en `app/services/challenge_generator.py`.
3. Integrar la llamada a Together AI (inferencia primero, sin esperar a que el fine-tuning con
   LoRA esté listo — se puede probar el pipeline completo con prompting mientras el dataset se
   termina de curar).
4. Una vez el fine-tuning con LoRA esté disponible, cambiar el modelo usado en la llamada sin
   tocar el resto del pipeline (la validación y el generador no cambian).
