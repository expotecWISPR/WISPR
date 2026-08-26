# Documentación de Arquitectura de Red, Software y Seguridad en AWS
## Proyecto: Plataforma CTF Educativa con IA (Together AI/Llama 3), Terminales Virtuales y Sandboxing Empresarial

> **⚠️ Nota importante:** Este documento describe una **arquitectura objetivo / nivel producción**, útil para
> explicar el concepto de Defensa en Profundidad en la defensa ante el profesor. **No es la arquitectura que se
> despliega para el desarrollo diario del MVP.** Para la versión simplificada, económica y realmente desplegada
> mientras se construye el proyecto, ver [arquitectura_mvp.md](arquitectura_mvp.md).
>
> **Corrección (actualizada 11 ago 2026):** este documento menciona que Llama 3 está "entrenado y
> ajustado específicamente" para retos de ciberseguridad. Precisando: se descartó el **fine-tuning
> completo** (reentrenar todos los parámetros) por requerir GPUs dedicadas y días de entrenamiento,
> inviable para el equipo. Sí se usa **LoRA** (fine-tuning parcial, mucho más liviano) vía el
> servicio administrado de fine-tuning de Together AI, con un dataset curado por el equipo
> (~500 ejemplos). El modelo con LoRA se usa específicamente para generar la *especificación* de
> los retos (JSON validado con Pydantic), no el archivo final — ver `docs/pipeline_ia_retos.md`.

Este documento detalla el diseño de la infraestructura de red en Amazon Web Services (AWS), la justificación táctica de ciberseguridad bajo el enfoque de **Defensa en Profundidad**, el desglose del stack tecnológico distribuido, el endurecimiento de hosts/APIs y la estimación financiera para la viabilidad del proyecto.

---

## 1. Justificación de Ciberseguridad y Gestión de Riesgos

### El Riesgo del Modelo Monolítico (Falta de Aislamiento)
Alojar una plataforma de entrenamiento en ciberseguridad que por diseño ejecuta herramientas ofensivas (`Aircrack-ng`, `Scapy`, `TShark`) y terminales interactivas reales (`node-pty` / `xterm.js`) en un único servidor consolidado representa una vulnerabilidad crítica de **Falta de Aislamiento de Compartimentos**.

Si un usuario malintencionado o un estudiante del CTF logra:
1. **Escape de Contenedor (Container Breakout):** Explotar una vulnerabilidad en el motor de Docker del WebShell.
2. **Escalada de Privilegios (Privilege Escalation):** Obtener acceso de raíz (`root`) en el sistema operativo host.

Al estar todo unificado en una sola instancia, el atacante obtendría acceso inmediato a la lógica de orquestación, las llaves API de servicios de Inteligencia Artificial externos, los tokens JWT de autenticación, la capacidad de interceptar la base de datos y comprometer la disponibilidad total de la plataforma.

### La Solución: Defensa en Profundidad (Defense in Depth)
Para mitigar este riesgo estructural, esta arquitectura se rige bajo el principio de **Defensa en Profundidad**, segmentando la aplicación en múltiples Docker Hosts distribuidos a lo largo de subredes aisladas en AWS. No se confía en una sola barrera de seguridad: si el atacante vulnera el contenedor del laboratorio, se enfrentará a controles a nivel de Kernel de Linux (seccomp/AppArmor), luego a firewalls de instancia (Security Groups) y finalmente a firewalls perimetrales de subred (Network ACLs).

---

## 2. Diagrama de la Arquitectura de Red (VPC)

El siguiente esquema ilustra la segmentación lógica de la red de AWS orientada a un entorno de producción seguro:

```text
   [ APLICACIÓN DE ESCRITORIO ] (React + Electron + xterm.js)
                 │
                 ▼ (Tráfico Seguro: HTTPS & WebSockets / Puertos 80, 443)
      [ Internet Gateway (IGW) ]
                 │
┌────────────────▼──────────────────────────────────────────────────────────┐
│ VPC Principal (Bloque CIDR: 10.0.0.0/16)                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 1. SUBRED PÚBLICA (DMZ) - CIDR: 10.0.1.0/24                         │  │
│  │    Ruta: 0.0.0.0/0 -> IGW                                           │  │
│  │                                                                     │  │
│  │    [ EC2: Web Backend/API ] (t3.small)                              │  │
│  │      └── Docker: FastAPI + Uvicorn + SQLAlchemy 2                   │  │
│  └────────────────────┬────────────────────────────────────────────────┘  │
│                       │                                                   │
│                       ▼ (Peticiones REST Internas / Canal Seguro)         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 2. SUBRED PRIVADA (Aplicaciones) - CIDR: 10.0.2.0/24                │  │
│  │    Ruta: Tráfico saliente a Internet a través de NAT Gateway        │  │
│  │                                                                     │  │
│  │    [ EC2: Análisis de Datos e IA ] (t3.medium)                      │  │
│  │      └── Docker: Scikit-learn + Pandas + Conexión a Together AI     │  │
│  └────────────────────┬────────────────────────────────────────────────┘  │
│                       │                                                   │
│                       ▼ (Orquestación de Sockets de Terminal)             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 3. SUBRED PRIVADA (Sandbox / Laboratorios) - CIDR: 10.0.3.0/24       │  │
│  │    NACL: Bloqueo explícito e irreversible hacia Subred Pública 10.0.1.0/24│  │
│  │                                                                     │  │
│  │    [ EC2: Docker Host / Retos CTF ] (t3.medium)                     │  │
│  │      └── Docker Dinámico: Retos controlados por seccomp/AppArmor    │  │
│  └────────────────────┬────────────────────────────────────────────────┘  │
│                       │                                                   │
│                       ▼ (Conexión Privada / Tráfico de Datos)             │
│          [ S3 VPC Gateway Endpoint ] ──► [ Amazon S3 Bucket ]            │
└───────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ├──► (Petición HTTPS API vía NAT Gateway) ──► [ TOGETHER AI (Llama 3) ]
                                 │
                                 ▼ (Puerto Saliente 5432 vía NAT Gateway) ──► [ SUPABASE (PostgreSQL) ]
```

---

## 3. Desglose del Stack Tecnológico por Componente

### 3.1 Interfaz y Aplicación Cliente (Frontend)
*   **React & Tailwind CSS:** Construcción de la interfaz de usuario modular, moderna y responsiva.
*   **Chart.js:** Renderizado de estadísticas de rendimiento y gráficas de progreso del usuario en los retos del CTF.
*   **Electron:** Contenedor nativo que empaqueta la aplicación web en un ejecutable de escritorio instalable multiplataforma (Windows/Linux/Mac), aislando el entorno de ejecución del navegador comercial tradicional.
*   **xterm.js:** Emulador de terminal embebido en la interfaz para interactuar con los retos en tiempo real.

### 3.2 Lógica de Negocio y Servidor (Backend)
*   **FastAPI & Uvicorn (Python 3.13):** Framework y servidor ASGI de alto rendimiento encargado de exponer las APIs REST y gestionar los túneles de WebSockets para la terminal interactiva.
*   **Pydantic & pydantic-settings:** Validación estricta de tipos de datos en los *endpoints* y gestión segura de variables de entorno (`.env`).
*   **SQLAlchemy 2 & Alembic:** ORM para interactuar con la persistencia de datos y motor de migraciones para el control de versiones de la estructura relacional.
*   **python-jose & passlib [bcrypt]:** Core de seguridad criptográfica. Generación, firma y verificación de tokens JWT para la sesión de los usuarios. Hashing seguro de contraseñas con bcrypt (las credenciales nunca se almacenan en texto plano).
*   **Flujo de la Terminal (WebSockets):** Cuando el alumno escribe en `xterm.js`, el backend en node-pty se conecta a FastAPI, el cual actúa como un *proxy de sockets* redirigiendo el comando de forma segura a través de la red privada de AWS hacia la Instancia 3. El usuario jamás toca el Docker Host directamente.

### 3.3 Motor de Inteligencia Artificial y Análisis
*   **Together AI & Llama 3:** El motor de IA fundamental de la plataforma utiliza el modelo **Llama 3**, consumido mediante la API de alto rendimiento de **Together AI**. El modelo está entrenado y ajustado específicamente con parámetros de diseño y aprovisionamiento de retos de ciberseguridad.
*   **Scikit-learn, Pandas, NumPy, Matplotlib:** Módulo complementario de Machine Learning que procesa las métricas de aciertos, errores y tiempos del usuario para ajustar dinámicamente la dificultad del camino de aprendizaje (*learning path*). Al estar aislado en la **Instancia 2**, se garantiza que los picos de cómputo matemático no afecten la navegación del usuario.

### 3.4 Persistencia (Base de Datos)
*   **PostgreSQL sobre Supabase:** Instancia de base de datos relacional PostgreSQL alojada en la nube de Supabase. El proyecto utiliza exclusivamente la capa de persistencia relacional del proveedor; la lógica de autenticación se gestiona en FastAPI mediante los tokens JWT propietarios. Comunicación establecida a través del driver `psycopg2-binary`.

---

## 4. Endurecimiento de la Red y Seguridad Perimetral en AWS

### 4.1 Network Access Control Lists (NACL) - Firewall de Subred
Se aplica una política restrictiva sin estado (*stateless*) a nivel de subred para aislar por completo el entorno de hacking:
*   **Subred de Destino:** `Subred-Privada-Labs (10.0.3.0/24)`
*   **Regla Inbound/Outbound:** `DENY` explícito a cualquier paquete con destino u origen en el rango de la DMZ pública (`10.0.1.0/24`).
*   **Objetivo:** Si un alumno vulnera el entorno de laboratorios, el enrutador de AWS interceptará y descartará cualquier intento de escaneo de puertos o ataque de movimiento lateral hacia el servidor web principal.

### 4.2 Security Groups (SG) - Firewall de Instancia (*Stateful*)
1. **`SG-Web-Publico`:** Permite tráfico de entrada únicamente en los puertos `80` (HTTP) y `443` (HTTPS) desde cualquier origen (`0.0.0.0/0`).
2. **`SG-IA-Privado`:** Permite tráfico de entrada en el puerto de la API interna (ej. `5000`) cuyo origen sea estrictamente el identificador de `SG-Web-Publico`. No se exponen IPs; solo la web le habla a la IA.
3. **`SG-Labs-Sandbox`:** Permite tráfico en los puertos dinámicos asignados a los contenedores y sockets de terminal cuyo origen provenga exclusivamente del backend de FastAPI en la red interna.

### 4.3 Mitigación de Vectores de Ataque Comunes
*   **Prompt Injection:** La entrada del usuario para la generación de retos mediante la IA de Together AI está estrictamente limitada a la selección de opciones predefinidas y un campo de texto corto fuertemente sanitizado y parseado por Pydantic, neutralizando ataques de inyección de directivas en Llama 3.

*   **Protección de API Keys Externas:** Las llaves de acceso para Supabase y la API secreta de Together AI residen únicamente como variables de entorno cifradas dentro de contenedores en las instancias protegidas en subredes privadas. Ninguna clave es expuesta ni compilada en el cliente de Electron.

---

## 5. Arquitectura de Aislamiento del Sandbox (Contenedores)

El servidor de laboratorios (**Instancia 3**) ejecuta un entorno altamente endurecido utilizando las características nativas del Kernel de Linux para evitar fugas de privilegios:

*   **Linux Namespaces:** Aíslan los procesos de la terminal del alumno (PID, Mount, Network, IPC, UTS), impidiendo que vean o interactúen con procesos del host o de otros estudiantes.
*   **seccomp (Secure Computing Mode):** Filtra y restringe las llamadas al sistema (*syscalls*) que los contenedores dinámicos pueden invocar. Se bloquean llamadas críticas como `mount`, `ptrace`, `sys_chroot` o modificaciones de configuración de red para evitar el escape del contenedor.
*   **AppArmor:** Perfil de seguridad que confina los contenedores a nivel de archivos, bloqueando la escritura o lectura en directorios críticos del sistema operativo host, incluso si el proceso interno corre como `root` dentro de Docker.

---

## 6. Especificaciones del Inventario de Hardware (AWS EC2 & S3)

Para un equipo de desarrollo de **4 usuarios**, se ha optimizado la infraestructura asignando recursos dedicados para garantizar la estabilidad de la IA y Docker sin sobredimensionar costos:

| Rol del Servidor | Tipo de Instancia | vCPUs | Memoria RAM | Almacenamiento (EBS) | Justificación Técnica |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend/Backend Web** | `t3.small` | 2 | 2 GB | 30 GB (gp3) | Maneja el tráfico HTTP/HTTPS de Electron y la lógica de sesiones de FastAPI. |
| **Motor de IA (Analytics)** | `t3.medium` | 2 | 4 GB | 30 GB (gp3) | Controla las peticiones HTTPS externas a Together AI y los algoritmos de Scikit-learn. |
| **Docker Host (Retos)** | `t3.medium` | 2 | 4 GB | 50 GB (gp3) | Espacio y memoria suficientes para levantar los contenedores dinámicos del CTF de forma simultánea. |
| **Almacenamiento de Objetos**| `Amazon S3` | N/A | Ilimitado | Pago por uso | Aloja archivos estáticos, retos del CTF e imágenes Docker base. |

---

## 7. Estimación Financiera del Proyecto (Presupuesto Mensual)

Tomando como base un presupuesto asignado de **\$300 - \$400 USD**, la arquitectura empresarial planteada está optimizada para operar de forma continua (24/7) durante un mes completo de pruebas y defensa académica manteniéndose holgadamente por debajo del límite:

*   **1x Instancia EC2 t3.small (Web/FastAPI):** ~$15.00 USD / mes
*   **2x Instancias EC2 t3.medium (IA y Sandbox Labs):** ~$60.00 USD / mes (\$30.00 c/u)
*   **Almacenamiento EBS (Discos de Estado Sólido gp3 dedicados):** ~$12.00 USD / mes
*   **AWS NAT Gateway (Salida segura a internet para subredes privadas hacia Together AI y Supabase):** ~$32.00 USD / mes
*   **Amazon S3 (Almacenamiento e intercambio privado por VPC Endpoint):** ~$3.00 USD / mes (según uso estándar)
*   **Costo Total Mensual Estimado:** **~$122.00 USD**

*Conclusión Económica:* El proyecto consume aproximadamente el **35% del presupuesto máximo disponible**, garantizando una arquitectura de nivel corporativo real, alta tolerancia a fallos en la demostración y un amplio margen financiero para pruebas de estrés o backups adicionales (el costo no incluye los tokens de la API de Together AI, que se manejan por separado bajo demanda).


