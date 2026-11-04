# WISPR — Despliegue en AWS

Registro del despliegue real del 4 de noviembre de 2026: qué se instaló en la EC2, cómo quedó
configurado y qué falló por el camino. Sirve para repetirlo en otra instancia o para entender la
actual.

## Estado

| Parte | Estado |
|---|---|
| Plataforma web en `http://3.140.124.203` | Funciona (registro, login y retos) |
| FastAPI y Node como servicios | Funcionan; arrancan solos al encender la EC2 |
| Imágenes de Kali (`wispr-ctf-kali`, `wispr-ctf-target`) | Construidas |
| Terminal Kali desde la web | Sin comprobar todavía |
| HTTPS y dominio | Pendiente |
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
- **Puertos abiertos:** 80 y 443 para todos, 22 solo desde la IP del equipo. Los puertos 8000 y
  8787 no se abren: solo los usa nginx dentro de la instancia.

## Pasos

Todo se ejecuta en la EC2 salvo donde dice lo contrario.

### 1. Entrar por SSH (desde la PC)

Windows exige que solo el usuario pueda leer la llave. En CMD:

```cmd
icacls "C:\ruta\wispr.pem" /inheritance:r
icacls "C:\ruta\wispr.pem" /grant:r "%USERNAME%:R"
ssh -i "C:\ruta\wispr.pem" ubuntu@3.140.124.203
```

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
WISPR_PUBLIC_HOSTS=$IP
INSTANCE_SECRET=$(openssl rand -hex 32)
KALI_MEMORY=768m
KALI_CPUS=1
MAX_LAB_ENVIRONMENTS=3
EOF
chmod 600 ~/WISPR-frontend/.env
```

`IP=...` es una variable de la sesión: se pierde al cerrar el SSH. Los límites de Kali son para los
4 GB de una t3.medium: como máximo 3 laboratorios a la vez. `npm ci` avisa de una vulnerabilidad
moderada; no se ejecutó `npm audit fix` durante el despliegue para no cambiar versiones.

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
sudo sed -i "s/server_name wispr\.ejemplo\.com;/server_name $IP;/" /etc/nginx/conf.d/wispr.conf
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

## Problemas que aparecieron

| Síntoma | Causa | Solución |
|---|---|---|
| La IP nueva no mostraba nada | El navegador intentaba `https://`, que todavía no existe | Escribir `http://3.140.124.203` completo |
| Seguía «Welcome to nginx» | Faltaban los pasos 4 a 6: sin servicios y con el sitio `default` activo | Hacer los pasos 4 a 6 |
| `unknown directive "la"` en `wispr.conf` | Un `sed` con `.*;` borró de más, porque el comentario de esa línea tenía otro `;` | Reemplazar solo `wispr.ejemplo.com`, como en el paso 6. El comentario ya se movió a otra línea |
| Cambio de IP al asociar la Elastic IP | La IP anterior desaparece y queda escrita en los `.env` y en nginx | Reemplazarla en `backend/.env`, `WISPR-frontend/.env` y `wispr.conf` |

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

## Pendiente

1. **Probar la terminal Kali** desde la web: abrir un reto y pulsar «Abrir en Kali».
2. **HTTPS con dominio:** apuntar el dominio a `3.140.124.203`, ejecutar
   `sudo certbot --nginx -d <dominio>` y cambiar a `https://<dominio>` en `CORS_ORIGINS` del backend
   y en `WISPR_PUBLIC_HOSTS` de Node (y `server_name` en nginx). Luego activar HSTS en `wispr.conf`.
3. **Electron:** fijar la dirección del servidor dentro de la app antes de construir el instalador.
4. **Separar la base de producción** de la de desarrollo si se va a usar con estudiantes reales.
