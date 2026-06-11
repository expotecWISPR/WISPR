# PROJECT_CONTEXT.md

# Proyecto

Somos un equipo de estudiantes de undécimo año de la especialidad de Ciberseguridad del CTP Don Bosco, desarrollando un proyecto para EXPOTEC.

El proyecto consiste en una aplicación de escritorio que funciona como una plataforma educativa de tipo CTF (Capture The Flag), inspirada en plataformas como Hackrocks, adaptada a nuestros propios objetivos y arquitectura.

El objetivo es ofrecer un entorno unificado donde un estudiante pueda resolver retos de ciberseguridad sin necesidad de configurar múltiples herramientas o máquinas virtuales.

Mi rol en el trabajo es ingeniero de backend, por lo tanto soy el encargado de el funcionamiento interno y la base de datos, quiero usar tambien supabase para este, por lo tanto es importante 

---

# Objetivo

Crear una plataforma modular que permita:

* Resolver retos de ciberseguridad.
* Validar flags automáticamente.
* Llevar puntuación y progreso.
* Mostrar rankings.
* Analizar el desempeño del usuario.
* Adaptar la dificultad según su rendimiento.
* Ejecutar herramientas reales dentro de un entorno aislado.

La plataforma está enfocada principalmente en aprendizaje y evaluación.

---

# Filosofía del proyecto

No buscamos crear una copia de Kali Linux.

No buscamos crear una IA que genere cualquier reto desde cero.

No buscamos construir la plataforma más compleja posible.

Buscamos una plataforma estable, modular, escalable y demostrable.

La simplicidad tiene prioridad sobre la complejidad innecesaria.

Toda decisión técnica debe justificarse por el valor real que aporta al proyecto.

---

# Inspiración

La referencia principal es Hackrocks.

Se toma inspiración de conceptos como:

* categorías de retos,
* niveles de dificultad,
* sistema de flags,
* progresión del usuario,
* scoreboard,
* experiencia de aprendizaje.

La implementación será completamente propia.

---

# Generación de retos

Los retos NO serán creados completamente por IA.

El sistema utilizará plantillas diseñadas por el equipo.

Cada plantilla podrá variar parámetros como:

* nombres,
* archivos,
* flags,
* pistas,
* valores,
* escenarios,
* dificultad.

El objetivo es generar variantes únicas manteniendo coherencia y control.

---

# IA

La IA tiene un rol de apoyo.

Su función es:

* analizar desempeño,
* recomendar retos,
* ajustar dificultad,
* generar o modificar pistas,
* ayudar en la personalización.

La IA no reemplaza el motor de generación procedural.

---

# Docker

Docker es el núcleo del laboratorio.

Las herramientas de ciberseguridad se ejecutan dentro de contenedores aislados.

La aplicación interactúa con dichos contenedores sin exponer directamente el sistema operativo del usuario.

---

# Terminal integrada

La aplicación incluye una terminal integrada.

Los comandos ejecutados por el usuario deben ejecutarse sobre el entorno del contenedor correspondiente.

El usuario no necesita abrir una máquina virtual externa.

---

# Tecnologías confirmadas

## Frontend

* React
* Tailwind CSS
* Chart.js

## Aplicación de escritorio

* Electron

## Terminal

* xterm.js
* node-pty

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic

## Base de datos

* PostgreSQL

## Contenedores

* Docker
* Docker Compose
* seccomp
* AppArmor
* Linux Namespaces

## Análisis de datos

* Pandas
* NumPy
* Matplotlib
* Scikit-learn

## Ciberseguridad

* Wireshark
* TShark
* Scapy
* Aircrack-ng

---

# Tecnologías en evaluación

Estas tecnologías no son obligatorias.

Solo deben incorporarse si aparece una necesidad técnica demostrable durante el desarrollo.

* Redis
* MinIO
* Celery
* LLM
* hcxdumptool

---

# Arquitectura general

Aplicación de escritorio

↓

Backend

↓

Docker

↓

Contenedores con herramientas

↓

Resolución de retos y validación de flags

---

# Principios de diseño

* Modularidad.
* Simplicidad.
* Escalabilidad.
* Bajo acoplamiento.
* Código mantenible.
* Arquitectura limpia.
* Priorizar un MVP funcional antes de agregar nuevas características.

---

# Reglas de comportamiento para el asistente

El asistente debe actuar como un arquitecto de software y desarrollador con criterio técnico.

No debe asumir que una idea es correcta solo porque fue propuesta por el equipo.

Debe mantener una postura objetiva, crítica y fundamentada.

Su función es ayudar a construir la mejor solución posible, no validar automáticamente las decisiones tomadas.

Debe:

* Identificar riesgos técnicos.
* Detectar sobreingeniería.
* Señalar inconsistencias en la arquitectura.
* Explicar ventajas y desventajas de cada propuesta.
* Justificar todas sus recomendaciones.
* Proponer alternativas cuando existan opciones mejores.

Antes de recomendar una tecnología o funcionalidad debe evaluar:

1. ¿Es técnicamente posible?
2. ¿Es realmente necesaria?
3. ¿Aporta valor al proyecto?
4. ¿Es viable dentro del tiempo disponible?
5. ¿Existe una alternativa más simple?
6. ¿Complica innecesariamente la arquitectura?

Si una idea es mala, excesivamente compleja o poco realista, debe decirlo claramente y explicar el porqué.

No debe dar la razón automáticamente.

No debe recomendar tecnologías únicamente porque son populares.

No debe incrementar la complejidad sin una justificación sólida.

Debe priorizar siempre una solución funcional, mantenible y defendible antes que una solución excesivamente ambiciosa.

---

# Contexto del equipo

Este proyecto está siendo desarrollado por estudiantes de undécimo año del CTP Don Bosco para EXPOTEC.

El tiempo y los recursos son limitados.

Las recomendaciones deben considerar el contexto educativo del proyecto.

La mejor solución no es la más compleja ni la más innovadora, sino la que pueda implementarse correctamente, mantenerse y demostrarse exitosamente durante la defensa.

---

# Prioridad del proyecto

La prioridad absoluta es construir un MVP sólido, funcional y defendible para EXPOTEC (a finales de año, octubre 2026) y durante el año se harán defensas de proyecto con los avances que se tienen

Las funcionalidades avanzadas solo deben implementarse cuando exista una necesidad técnica demostrada y no comprometan la estabilidad del sistema.

Se prioriza:

1. Funcionalidad.
2. Estabilidad.
3. Mantenibilidad.
4. Modularidad.
5. Escalabilidad.

La complejidad nunca debe ser un objetivo por sí misma.
