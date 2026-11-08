# WISPR — Despliegue en AWS

Registro del despliegue real del 4 de noviembre de 2026, actualizado el 7 de noviembre con el
dominio y los laboratorios: qué se instaló en la EC2, cómo quedó configurado y qué falló por el
camino. Sirve para repetirlo en otra instancia o para entender la actual.

## Estado

| Parte | Estado |
|---|---|
| Plataforma web en `http://3.140.124.203` | Funciona (registro, login y retos) |
| FastAPI y Node como servicios | Funcionan; arrancan solos al encender la EC2 |
| Imágenes de Kali (`wispr-ctf-kali`, `wispr-ctf-target`) | Construidas |
| Terminal Kali desde la web | Arranca laboratorios por la IP; falta una sesión completa |
| Dominio `wispr.training` en Node | Hecho: Node lo acepta (comprobado desde fuera el 7 nov) |
| Dominio en `server_name` de nginx | Sin confirmar: `grep server_name /etc/nginx/conf.d/wispr.conf` (paso 6) |
| DNS de `wispr.training` | Pendiente: sobran dos registros «Parked» de GoDaddy (ver [Dominio](#dominio-wisprtraining)) |
| Laboratorios que se liberan solos | En GitHub (`WISPR-frontend` `b128621`); falta `git pull` en la EC2 |
| HTTPS | Pendiente (con el DNS ya limpio) |
| Electron apuntando al servidor | Pendiente |

## Cómo quedó

```
Navegador ── http :80 ──► nginx ──┬─► FastAPI  127.0.0.1:8000  (servicio wispr-api)
                                  └─► Node     127.0.0.1:8787  (servicio wispr-web) ──► Docker (Kali)
FastAPI ──► Supabase (la misma base que en desarrollo), Together AI, Gmail SMTP
```

- **Instancia:** Ubuntu 24.04, usuario `ubuntu`. La red (VPC, subred, Security Group, tabla de
  enrutamiento e Internet Gateway) la creó el equipo antes del despliegue.
- **Elastic IP:** `3.140.124.203`. Es la dirección fija; no cambia al detener y encender la EC2.
- **Código:** `/home/ubuntu/WISPR` y `/home/ubuntu/WISPR-frontend`, clonados de GitHub.
- **Dominio:** `wispr.training` y `www.wispr.training`, comprados en GoDaddy.
- **Puertos abiertos:** 80 y 443 para todos, 22 solo desde las IPs que el equipo agregó al Security
  Group. Los puertos 8000 y 8787 no se abren: solo los usa nginx dentro de la instancia.

## Pasos

Todo se ejecuta en la EC2 salvo donde dice lo contrario.

### 1. Entrar por SSH (desde la PC)

Windows exige que solo el usuario pueda leer la llave. En CMD:

```cmd
icacls "C:\ruta\wispr.pem" /inheritance:r
icacls "C:\ruta\wispr.pem" /grant:r "%USERNAME%:R"
ssh -i "C:\ruta\wispr.pem" ubuntu@3.140.124.203
```

En Linux o Mac la llave va en `~/.ssh` y solo el dueño puede leerla:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
mv ~/Downloads/WISPR-Keypair.pem ~/.ssh/
chmod 400 ~/.ssh/WISPR-Keypair.pem
ssh -i ~/.ssh/WISPR-Keypair.pem ubuntu@3.140.124.203
```

Si `ssh` se queda esperando y termina en `Connection timed out`, el Security Group no deja entrar
desde esa red: en la consola de AWS, EC2 → la instancia → pestaña **Security** → el Security Group
→ **Edit inbound rules** → **Add rule**, tipo **SSH**, origen **My IP**. No usar `0.0.0.0/0`.

La llave `.pem` nunca se sube a GitHub ni se comparte.

### 2. Herramientas

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git nginx python3-venv python3-pip docker.io build-essential
sudo usermod -aG docker ubuntu
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

Después hay que salir (`exit`) y volver a entrar para que valga el permiso de Docker. Node va en la
versión 22 porque la de Ubuntu es demasiado vieja; `build-essential` hace falta para compilar
`node-pty`.

### 3. Código y backend

```bash
cd ~
git clone https://github.com/expotecWISPR/WISPR.git
git clone https://github.com/expotecWISPR/WISPR-frontend.git
cd ~/WISPR/backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

El `.env` no está en GitHub. Se copia desde la PC (en PowerShell o CMD, no dentro del SSH):

```cmd
scp -i "C:\ruta\wispr.pem" "C:\Users\...\WISPR\backend\.env" ubuntu@3.140.124.203:/home/ubuntu/WISPR/backend/.env
```

En la EC2 se protege y se ajusta:

```bash
chmod 600 ~/WISPR/backend/.env
nano ~/WISPR/backend/.env
```

```
ENVIRONMENT=production
CORS_ORIGINS=http://3.140.124.203
AWS_ACCESS_KEY_ID=no-usado
AWS_SECRET_ACCESS_KEY=no-usado
AWS_REGION=no-usado
S3_BUCKET_NAME=no-usado
```

- **Campos de AWS:** el backend no los usa (S3 no está integrado), pero `app/core/config.py` los
  exige. Van con relleno: no crear claves de IAM reales solo para esto.
- **Comprobar Supabase:** `venv/bin/python -m alembic -c migrations/alembic.ini current` debe mostrar
  `e8b3a6f42c17 (head)`. La base ya tenía las migraciones y los 14 retos, así que no hizo falta
  `alembic upgrade` ni el seed.

### 4. Frontend y Node

```bash
IP=3.140.124.203
cd ~/WISPR-frontend
npm ci
cat > ~/WISPR-frontend/.env <<EOF
WISPR_BACKEND_URL=http://127.0.0.1:8000
WISPR_PUBLIC_HOSTS=$IP,wispr.training,www.wispr.training
INSTANCE_SECRET=$(openssl rand -hex 32)
KALI_MEMORY=768m
KALI_CPUS=1
MAX_LAB_ENVIRONMENTS=3
EOF
chmod 600 ~/WISPR-frontend/.env
```

- `IP=...` es una variable de la sesión: se pierde al cerrar el SSH.
- **`WISPR_PUBLIC_HOSTS` lleva todas las direcciones con las que se abre WISPR.** Node rechaza con
  403 cualquier petición cuyo `Origin` no esté en la lista. El 4 nov solo se puso la IP, y al entrar
  por el dominio la página cargaba pero la terminal no abría. Se corrigió el 7 nov.
- **Límites de Kali:** son para los 4 GB de una t3.medium, como máximo 3 laboratorios a la vez. Un
  laboratorio se detiene solo tras 10 minutos sin que nadie escriba en su terminal
  (`LAB_IDLE_MINUTES`). Ver [Laboratorios](#laboratorios-kali) en Mantenimiento.
- `npm ci` avisa de una vulnerabilidad moderada. No se ejecutó `npm audit fix` durante el despliegue,
  para no cambiar versiones.

### 5. Servicios

```bash
sudo tee /etc/systemd/system/wispr-api.service > /dev/null <<'EOF'
[Unit]
Description=WISPR FastAPI
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/WISPR/backend
ExecStart=/home/ubuntu/WISPR/backend/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/wispr-web.service > /dev/null <<'EOF'
[Unit]
Description=WISPR Node (frontend y terminal Kali)
After=network-online.target docker.service wispr-api.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/WISPR-frontend
ExecStart=/usr/bin/node server.js
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now wispr-api wispr-web
```

FastAPI corre con **un solo proceso** a propósito: los códigos de verificación viven en memoria.
Node lee su `.env` por su cuenta.

### 6. nginx

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo cp ~/WISPR/deploy/nginx/wispr.conf /etc/nginx/conf.d/wispr.conf
sudo sed -i "s/server_name wispr\.ejemplo\.com;/server_name wispr.training www.wispr.training $IP;/" /etc/nginx/conf.d/wispr.conf
sudo nginx -t && sudo systemctl reload nginx
```

El 4 nov se puso solo la IP. En una instancia que ya tiene `server_name 3.140.124.203;`, el dominio
se agrega con:

```bash
sudo sed -i 's/server_name 3\.140\.124\.203;/server_name wispr.training www.wispr.training 3.140.124.203;/' /etc/nginx/conf.d/wispr.conf
grep server_name /etc/nginx/conf.d/wispr.conf
sudo nginx -t && sudo systemctl reload nginx
```

### 7. Imágenes de Kali

Tardan unos 25 minutos. Con `nohup` siguen aunque se corte el SSH:

```bash
cd ~/WISPR-frontend
nohup sh -c 'docker build --tag wispr-ctf-kali:local --file kali/Dockerfile . && docker build --tag wispr-ctf-target:local --file kali/target/Dockerfile kali/target' > ~/kali-build.log 2>&1 &
```

Quedaron en 2.3 GB (`wispr-ctf-kali`) y 74 MB (`wispr-ctf-target`). Node solo las construye si no
existen: si cambia la carpeta `kali/`, hay que reconstruirlas a mano.

### 8. Comprobar

```bash
systemctl is-active wispr-api wispr-web nginx
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/
sudo journalctl -u wispr-api -u wispr-web -n 40 --no-pager
```

Deben salir tres `active` y un `200`. El último comando muestra los errores de los servicios.

Para comprobar que Node acepta el dominio (sin depender del DNS):

```bash
curl -s -H "Origin: http://wispr.training" http://127.0.0.1/api/platform/status; echo
curl -s -H "Origin: http://www.wispr.training" http://127.0.0.1/api/platform/status; echo
```

Las dos líneas deben empezar con `{"ok":true`. Si dicen `Acceso local requerido`, falta esa dirección
en `WISPR_PUBLIC_HOSTS` (paso 4), o Node no se reinició después de cambiarla.

## Problemas que aparecieron

| Síntoma | Causa | Solución |
|---|---|---|
| La IP nueva no mostraba nada | El navegador intentaba `https://`, que todavía no existe | Escribir `http://3.140.124.203` completo |
| Seguía «Welcome to nginx» | Faltaban los pasos 4 a 6: sin servicios y con el sitio `default` activo | Hacer los pasos 4 a 6 |
| `unknown directive "la"` en `wispr.conf` | Un `sed` con `.*;` borró de más, porque el comentario de esa línea tenía otro `;` | Reemplazar solo `wispr.ejemplo.com`, como en el paso 6. El comentario ya se movió a otra línea |
| Cambio de IP al asociar la Elastic IP | La IP anterior desaparece y queda escrita en los `.env` y en nginx | Reemplazarla en `backend/.env`, `WISPR-frontend/.env` y `wispr.conf` |
| Con el dominio, a veces aparece la página de GoDaddy | El dominio tiene tres registros A: el de la EC2 y dos «Parked» de GoDaddy; cada visita elige uno al azar | Borrar los «Parked» en GoDaddy (ver [Dominio](#dominio-wisprtraining)) |
| Por el dominio carga la página, pero la terminal no abre | Node rechaza con 403 el `Origin` que no está en `WISPR_PUBLIC_HOSTS`, y solo estaba la IP | Agregar el dominio y `www` (paso 4) y reiniciar `wispr-web` |
| «Límite de 3 laboratorios activos» al abrir la terminal | Un laboratorio solo liberaba su espacio con «Detener entorno», y el contador vivía en memoria | Desde `b128621` se liberan solos tras 10 minutos sin uso. Limpieza manual en [Laboratorios](#laboratorios-kali) |
| `ssh` termina en `Connection timed out` | El Security Group solo deja entrar por el 22 desde las IPs agregadas | Agregar una regla SSH con origen «My IP» (paso 1) |

## Dominio `wispr.training`

En GoDaddy, **Mis productos → wispr.training → DNS → Registros**, deben quedar solo estos dos:

| Tipo | Nombre | Valor |
|---|---|---|
| A | `@` | `3.140.124.203` |
| CNAME | `www` | `@` |

- GoDaddy crea un registro A «Parked» que lleva a su página de estacionamiento. Si queda junto al de
  la EC2, el navegador elige uno al azar en cada visita. Revisado el 7 nov: todavía responden
  `3.33.130.190` y `15.197.148.33` (GoDaddy) además de la EC2.
- En **Reenvío (Forwarding)** no debe haber nada activo.
- Los registros duran 10 minutos en caché, así que el cambio se ve en unos 10 minutos.
- **Comprobar:** `dig +short wispr.training` en Linux, o `nslookup wispr.training` en Windows, debe
  responder solo `3.140.124.203`.
- `certbot` necesita el DNS limpio: si Let's Encrypt cae en una IP de GoDaddy, la validación falla.

## Mantenimiento

**Actualizar el código** después de un push:

```bash
cd ~/WISPR && git pull
cd ~/WISPR-frontend && git pull && npm ci
cd ~/WISPR/backend && venv/bin/pip install -r requirements.txt
venv/bin/python -m alembic -c migrations/alembic.ini upgrade head
sudo systemctl restart wispr-api wispr-web
```

**Encender y apagar:** detener la EC2 con **Stop**, nunca Terminate, porque Terminate la borra. Al
encenderla, los servicios arrancan solos.

**Voucher de admin:** la EC2 usa la misma base que desarrollo, así que el voucher de `admin_wispr`
también vale aquí. Se emite uno nuevo desde `~/WISPR/backend` con
`venv/bin/python -m app.services.admin_voucher admin_wispr`, y el anterior deja de servir.

### Laboratorios Kali

Cada jugador que abre la terminal tiene un contenedor Kali y uno objetivo. Desde `WISPR-frontend`
`b128621`:

- **Se liberan solos.** Un laboratorio se detiene tras `LAB_IDLE_MINUTES` (10 por defecto) sin que
  nadie escriba en su terminal, esté abierta o cerrada. Si estaba abierta, se cierra con un aviso.
  Los archivos de `/workspace` se conservan; lo que estaba en `/tmp` o en el home se pierde.
- **El límite cuenta los contenedores que corren en Docker** (`MAX_LAB_ENVIRONMENTS`), así que un
  reinicio de Node ya no lo desajusta.
- **El límite solo afecta la terminal.** Con el límite lleno, cualquiera puede entrar a la página,
  ver retos y teoría, descargar archivos y enviar flags.

Ver qué hay encendido y cuánta memoria usa:

```bash
docker ps -a --filter name=wispr-
docker stats --no-stream
free -h
```

Liberar todo a mano (corta las terminales abiertas):

```bash
docker ps -aq --filter name=wispr-kali- | xargs -r docker rm -f
docker ps -aq --filter name=wispr-target- | xargs -r docker rm -f
sudo systemctl restart wispr-web
```

Borrar los contenedores no hace perder archivos: Node los vuelve a crear cuando ese jugador abre la
terminal.

**Capacidad.** Cada laboratorio puede llegar a usar ~0,9 GB de RAM (768 MB Kali + 128 MB objetivo),
además de ~0,7 GB del sistema, FastAPI, Node y Docker (estimado). La EC2 no tiene swap: si la RAM se
llena, primero todo va lento y después el kernel mata procesos.

| Instancia | RAM | `MAX_LAB_ENVIRONMENTS` recomendado |
|---|---|---|
| t3.medium (uso normal) | 4 GB | 3 |
| t3.large (día de EXPOTEC) | 8 GB | 6 |

El volumen de 30 GiB es disco, no RAM: no cambia este cálculo.

**Cambiar a t3.large para EXPOTEC.** En la consola: la instancia → **Stop** → **Actions → Instance
settings → Change instance type** → `t3.large` → **Start**. La Elastic IP, el volumen y los servicios
se conservan. Después, por SSH, se cambia el límite y se reinicia Node:

```bash
sed -i 's/^MAX_LAB_ENVIRONMENTS=.*/MAX_LAB_ENVIRONMENTS=6/' ~/WISPR-frontend/.env
sudo systemctl restart wispr-web
```

Cuesta aproximadamente US$1 más por día. Al terminar, se hace lo mismo con `t3.medium` y
`MAX_LAB_ENVIRONMENTS=3`.

## Pendiente

1. **Limpiar el DNS** de `wispr.training` (ver [Dominio](#dominio-wisprtraining)).
2. **Traer el cambio de los laboratorios:** `cd ~/WISPR-frontend && git pull && sudo systemctl
   restart wispr-web` (no hace falta `npm ci`). Luego probar una sesión completa: abrir un reto,
   pulsar «Abrir en Kali», usar `ctf show` y `ctf submit`.
3. **HTTPS**, con el DNS ya limpio:
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d wispr.training -d www.wispr.training
   ```
   `WISPR_PUBLIC_HOSTS` no cambia: Node compara solo el nombre, no `http`/`https`. Poner
   `CORS_ORIGINS=https://wispr.training,https://www.wispr.training` en `backend/.env`, reiniciar
   `wispr-api` y activar la línea de HSTS en `wispr.conf`.
4. **Electron:** fijar la dirección del servidor dentro de la app antes de construir el instalador.
5. **Separar la base de producción** de la de desarrollo si se va a usar con estudiantes reales.
