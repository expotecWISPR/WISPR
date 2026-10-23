# Sesión del 22 de octubre de 2026

Resumen de todo lo que se hizo el 22 de octubre: qué cambió, cómo funciona por dentro y cómo
probarlo. Para el detalle histórico completo está `CLAUDE.md` (sección "Progreso técnico").

**Repos:** `WISPR` (backend, Electron, documentación) y `WISPR-frontend` (web, servidor Node,
terminal Kali).

---

## 0. El flujo completo de WISPR (cómo encaja todo)

```
Estudiante
   │
   ├── App de escritorio (Electron)  ─┐
   └── Navegador                     ─┤  http://127.0.0.1:8787  (en AWS: nginx)
                                      ▼
                         Node (WISPR-frontend/server.js)
                         · sirve la web (app.js, style.css)
                         · terminal Kali: WebSocket + Docker + node-pty
                         · todo lo demás de /api/ → lo reenvía a FastAPI
                                      │
                                      ▼
                         FastAPI (WISPR/backend, puerto 8000)
                         · cuentas, MFA, sesiones
                         · retos, flags, puntos, bonos, cronómetro
                         · generación de retos (código + historia de la IA)
                         · grupos, admin, recorrido de bienvenida
                                      │
                                      ▼
                         Supabase (PostgreSQL, por el Session Pooler IPv4)
```

**Recorrido de un estudiante nuevo:**

1. Se registra y confirma con el código que llega al correo (MFA).
2. **Primera vez:** Wisp le muestra la plataforma en 8 pasos (sección 6).
3. Abre un reto. Arranca su **cronómetro**, que guarda el servidor (sección 4).
4. Descarga el archivo. Si el reto tiene generador, el archivo y la flag son **solo suyos**.
5. Lo analiza en la terminal Kali, dentro de la plataforma.
6. Envía la flag, desde la web o con `ctf submit`. FastAPI calcula los puntos con las pistas, los
   fallos, la velocidad y la racha, y guarda el desglose.
7. El motor adaptativo le recomienda el siguiente reto según cómo le fue. También puede **pedir
   retos de práctica**, que ahora suman puntos (sección 3).

---

## 1. App de escritorio con Electron

**Dónde:** `WISPR/electron/` (ver `electron/README.md`).

**Qué hace:** abre una ventana que carga WISPR desde el servidor. **No trae una copia del
frontend:** muestra la misma página que el navegador, así que todo lo que se cambia en la web
aparece solo en la app.

**Cómo funciona:**
- `main/index.js` crea una ventana de 1366×860 que carga `WISPR_URL` (por defecto
  `http://127.0.0.1:8787`; en AWS sería la dirección pública).
- **Seguridad:**
  - `contextIsolation` + `sandbox`, sin `nodeIntegration`: la página no puede usar Node ni tocar
    el equipo.
  - Solo navega dentro de WISPR; los enlaces externos se abren en el navegador del sistema.
  - Niega todos los permisos (cámara, micrófono, etc.).
  - Solo se puede abrir una ventana a la vez.
- Si el servidor no responde, muestra `main/offline.html` («No se pudo conectar con WISPR» y un
  botón «Reintentar»).
- `preload/index.js` solo expone `window.wisprDesktop` (`isDesktop`, `platform`), para que la web
  sepa que corre en la app.

**Cómo abrirla:** `cd electron` → `npm install` (la primera vez) → `npm start`.
Ojo: dentro de VS Code / Claude Code existe la variable `ELECTRON_RUN_AS_NODE=1` y hay que
quitarla para que abra.

---

## 2. Cuatro técnicas nuevas en el catálogo de la IA

Antes la IA solo podía generar retos de XOR y WEP. Ahora hay **6 técnicas**, cada una con 3
niveles **reales**: el método que sirve en un nivel falla en el siguiente.

| Técnica | Fácil | Medio | Difícil |
|---|---|---|---|
| `caesar_vigenere` (criptografía) | ROT13 | César con otro desplazamiento | Vigenère con llave de 3-5 letras |
| `encoding_layers` (misc) | base64 | 2 capas (base64/hex/base32) | 3-4 capas mezcladas |
| `http_plaintext_pcap` (redes) | POST con la flag en JSON | Entre ruido, en un formulario | En base64, partida en 2 paquetes TCP, con señuelos |
| `stego_png` (estego) | Metadato del PNG | Base64 después del final del PNG | En el bit menos significativo del canal rojo |

**Cómo funciona (igual que XOR/WEP):**
1. El **código** decide la técnica, el nivel y la flag (aleatoria, distinta por jugador).
2. La **IA** (Together AI; desde el 23 oct, Muse Glimmer 30B en vez de Llama 3.3) solo escribe la historia: título, descripción y una pista. Si falla,
   se usa una plantilla.
3. El **generador** (`challenge_generator.py`) construye el archivo de ese jugador.

**Archivos:**
- `app/schemas/challenge.py`: lista fija de técnicas (`TechniqueId`).
- `app/services/challenge_generator.py`: los generadores.
- `app/services/technique_info.py`: los textos de cada nivel.
- `app/services/ai_advisor.py`: las plantillas de respaldo.

Hay un reto Foundation de cada técnica en el catálogo (14 retos en total).

**Kali:** se agregaron `exiftool`, `binwalk` y `python3-pil` a `kali/Dockerfile` para poder
resolverlos. Los 12 archivos (4 técnicas × 3 niveles) se resolvieron dentro de Kali real con los
comandos de las pistas.

---

## 3. Los retos de práctica ahora suman puntos

Antes un reto que pedía el estudiante valía 0 puntos, para que nadie inflara el ranking pidiendo
retos fáciles. Ahora **sí suman**, pero cada vez menos si se repite la misma técnica y el mismo
nivel:

| Pedido de la misma técnica + nivel | Puntos |
|---|---|
| 1.º | 100 % |
| 2.º | 50 % |
| 3.º | 25 % |
| 4.º en adelante | 0 |

- También cuentan los pedidos sin resolver: pedir 5 de golpe no los cobra todos al 100 %.
- El formulario de la web muestra **cuánto valdrá** el reto antes de pedirlo.
- **Cómo funciona:**
  - `challenge_factory.PRACTICE_DECAY = (1.0, 0.5, 0.25)`.
  - Columna nueva `challenges.purpose`: `practice` (lo pidió el estudiante), `adaptive` (lo creó
    el motor), `class` (lo publicó un profesor) o vacío (catálogo).

---

## 4. Cronómetro, bonos y penalizaciones

### Las reglas

Todo está en **un solo archivo**, `app/services/bonus.py`, que usan la web, la terminal y las
pistas. Sobre los puntos del reto:

| Regla | Efecto |
|---|---|
| Cada pista abierta antes de resolver | −15 % |
| Cada intento fallido | −5 % (máximo −25 %) |
| Resolver en menos de 10 minutos | +15 % |
| Racha limpia (retos seguidos sin pistas ni fallos) | +5 % por cada uno que ya llevas (máximo +25 %) |

- **Racha limpia:** el 1.º reto limpio aún no da bono; el 2.º da +5 %, el 3.º +10 %… hasta +25 %.
  Un acierto con pistas o fallos la corta. Los retos de 0 puntos ni la suman ni la cortan.
- El total nunca baja de 0.
- **Ejemplo:** reto de 200 pts, 1 pista y 1 fallo, resuelto en 6 minutos:
  200 − 30 (pista) − 10 (fallo) + 30 (velocidad) = **190 pts**.

### Cómo funciona el cronómetro

1. Al abrir un reto por primera vez, la web llama a `POST /api/challenges/{id}/start` y el
   **servidor** guarda la hora en la tabla `challenge_timers`. La hora la decide el servidor, no
   el navegador, así nadie la puede adelantar.
2. `GET /api/challenges` devuelve `startedAt` de cada reto, la hora del servidor (`serverNow`,
   para corregir el reloj de la computadora) y las reglas (`scoring`).
3. Al acertar, `scoring.submit_flag` calcula el desglose con `bonus.breakdown(...)` y lo guarda
   en `solves.breakdown`; `solves.clean` marca si fue limpio.
4. `ctf submit` en la terminal muestra el desglose en una línea.

### Cómo se ve

- **Página del reto:** solo un anillo con el tiempo, a la derecha del título (debajo en el
  celular).
  - Verde mientras corre el bono de 10 minutos.
  - Naranja en los últimos 2 minutos.
  - Gris cuando ya no hay bono.
  - Al resolver queda verde con el tiempo final.
- **Pestaña Terminal:** una versión pequeña con el tiempo y los puntos.
- El anillo se actualiza cada segundo **sin redibujar la página**.

### Error encontrado y arreglado

Las respuestas lentas del servidor (1-3 segundos con Supabase) redibujaban la página y **borraban
la flag que el estudiante estaba escribiendo**. Pasaba al abrir una pista, al arrancar el
cronómetro y al enviar la flag. Ahora:
- lo escrito se guarda como borrador por reto (`flagDrafts`);
- al redibujar se devuelven el foco y el cursor al campo;
- arrancar el cronómetro ya no redibuja la página.

---

## 5. Cambios visuales

- **Inicio:** el anillo de «% completado» es más grande, centrado y separado del borde.
- **Cronómetro:** pasó de tarjeta grande con emojis, a tarjeta compacta, a **solo el anillo**
  (pedido del usuario). Las reglas se explican ahora en el recorrido de Wisp.

---

## 6. Recorrido de bienvenida con Wisp

### Qué ve el estudiante

La **primera vez** que un estudiante entra, la página se oscurece y Wisp (la mascota,
`img/mascot.png`) lo guía en 8 pasos, iluminando cada parte de la que habla:

| # | Se ilumina | Wisp explica |
|---|---|---|
| 1 | — (centrado) | Bienvenida |
| 2 | Anillo de avance | Qué porcentaje de retos resolvió |
| 3 | Pestaña Retos | Evidencia, flag `WISPR{…}` y puntos |
| 4 | Pestaña Teoría | Módulos con lección, práctica y quiz |
| 5 | Pestaña Terminal | Kali real, `ctf hint` y `ctf submit` |
| 6 | Pestaña Ranking | Competir con los compañeros |
| 7 | — (centrado) | Las reglas de puntos (sección 4) |
| 8 | Su nombre | Su progreso, con el botón «Ir a mi primer reto» |

- **Controles:** Atrás, Siguiente, Saltar recorrido, flechas del teclado y Esc.
- **Celular:** abre el menú de hamburguesa para iluminar las pestañas.
- **Repetirlo:** botón «Ver el recorrido de Wisp» en Progreso.
- **Quién lo ve:** solo estudiantes. Profesor y admin no.

### Cómo funciona

1. `/api/players/me` devuelve `tourSeen` (sale de la columna nueva `users.tour_seen_at`).
2. Cuando la web termina de cargar (`hydratePlatform`), si es estudiante y `tourSeen` es
   `false`, arranca el recorrido (`maybeStartTour`).
3. Al terminarlo o saltarlo, la web llama a `POST /api/players/tour` y el servidor guarda la
   hora. Por eso **no se repite**, aunque entre desde otra computadora o desde Electron.
4. **Dibujo:**
   - El recorrido se dibuja como una capa encima de la página (`mountTour`).
   - El «hueco» iluminado es una caja con una sombra enorme: todo lo que queda fuera se
     oscurece.
   - La burbuja de Wisp se coloca debajo de esa parte, o encima si no cabe (`positionTour`), y
     se reacomoda al cambiar el tamaño de la ventana o hacer scroll.
5. Los pasos y sus textos están en `TOUR_STEPS` (`app.js`). **Para cambiar un texto, se edita
   ahí.**

---

## 7. Base de datos: migraciones nuevas

Todas ya están **aplicadas** en Supabase. En AWS (Persona 2) hay que correr
`alembic upgrade head`:

| Migración | Qué agrega |
|---|---|
| `d7a4f19c3e58` | `challenges.purpose` (práctica / adaptativo / clase) |
| `e2b8c6d05a71` | Tabla `challenge_timers`, `solves.clean`, `solves.breakdown` |
| `f4c1a8e93b26` | `users.tour_seen_at` (recorrido de Wisp) |

Antes del 22 oct ya estaban `8f1d3c6a2b47` (grupos/admin) y `b3e9a7d41c20` (pistas con costo).
Después, `python -m app.db.seed_challenges` para cargar los 14 retos.

## 8. Rutas nuevas de la API

| Ruta | Para qué |
|---|---|
| `POST /api/challenges/{id}/start` | Arranca el cronómetro del reto (solo la primera vez) |
| `POST /api/players/tour` | Marca el recorrido de Wisp como visto |
| `GET /api/challenges` | Ahora también trae `scoring`, `serverNow` y `startedAt` |
| `GET /api/challenges/options` | Ahora también trae `practicePoints` para el estudiante |
| `GET /api/players/me` | Ahora también trae `cleanStreak`, `timers` y `tourSeen` |

## 9. Pruebas

- **244 tests** del backend pasan
  (`cd backend` → `venv\Scripts\python.exe -m pytest -q`).
- Probado en Chromium (Playwright), en escritorio y en celular (390 px), con un estudiante
  temporal que se borró al terminar:
  - el cronómetro en todos sus estados;
  - que la flag no se borre;
  - el recorrido de Wisp completo (aparece una sola vez, Esc lo cierra);
  - sin desbordes ni errores de JavaScript.
- Las 4 técnicas nuevas, resueltas en Kali real.

## 10. Cómo arrancar todo en local

1. Terminal 1: `cd backend` → `venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000`
2. Terminal 2: `cd ..\WISPR-frontend` → `node server.js`
3. Abrir http://127.0.0.1:8787, o la app: `cd electron` → `npm start`.
4. Docker Desktop abierto para la terminal Kali. Si cambió `kali/`, reconstruir la imagen:
   `docker build --tag wispr-ctf-kali:local --file kali/Dockerfile .` (desde `WISPR-frontend`).

## 11. Qué sigue

1. **Despliegue en AWS (Persona 2):** Session Pooler de Supabase, las migraciones, el seed y
   construir la imagen de Kali desde cero.
2. **Ensayo completo de la demo** en la máquina final.
3. **Teoría, Módulos 4 y 6:** los escribe el equipo (guía en
   `WISPR-frontend/docs/MODULOS-TEORIA.md`).
4. **Decisión pendiente:** la «racha» del ranking sigue contando envíos correctos seguidos, no la
   racha limpia de los bonos. ¿Unificarlas?
5. **Opcional:** instalador `.exe` de Electron (`electron-builder`).
