# WISPR — Pipeline de Generación de Retos con IA

Este documento detalla cómo la IA participa en la creación de retos sin perder control ni
coherencia sobre lo que finalmente se le entrega al estudiante. Complementa las secciones
"Generación de retos" e "IA" de `CLAUDE.md`.

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
   │  Together AI · Llama 3.3 70B + LoRA           │
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
  "flag": "FLAG{wep_died_for_a_reason}",
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
