"""
Envío del código de verificación MFA por correo.

Migrado de `sendVerificationCode`/`deliverDevCode` en
wispr_terminal_professional/server.js (ahí usaba nodemailer; acá usamos
`smtplib`, de la librería estándar de Python — sin dependencia nueva).

Dos modos:
- Con `SMTP_HOST` configurado: intenta enviar el correo real. Si falla
  (credenciales malas, SMTP caído, etc.), **no bloquea** el registro/login
  — cae automáticamente al modo desarrollo.
- Sin `SMTP_HOST`: modo desarrollo directo. El código se imprime en el log
  del servidor y se escribe en `backend/data/outbox/` (carpeta en
  .gitignore), igual que hacía el prototipo con `lab/data/outbox/`.

Nota de seguridad ya señalada en wispr_terminal_professional/docs/BACKEND-
PENDIENTE.md (punto 3.1.3): en producción, el modo desarrollo anula el MFA
por completo (el código viaja en la propia respuesta HTTP). Antes de
exponer esto fuera de una red de confianza, hay que hacer que falle en vez
de caer a este modo — pendiente, no resuelto en esta migración.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Literal

from app.core.config import settings

logger = logging.getLogger("wispr.email")

OUTBOX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "outbox"

def _subject(code: str) -> str:
    """El código va en el asunto (14 oct): con un asunto fijo, Gmail juntaba
    todos los correos (registro y cada login) en una sola conversación y era
    fácil copiar un código viejo — que ya no sirve, porque cada login nuevo
    invalida el anterior. Así cada correo es único y el código se ve en la
    notificación sin abrirlo."""
    return f"WISPR: tu código es {code}"


Purpose = Literal["register", "login"] | None

_INTRO = {
    "register": "Recibimos una solicitud para crear una cuenta de WISPR con",
    "login": "Recibimos un inicio de sesión en tu cuenta de WISPR con",
    None: "Recibimos una solicitud de verificación para",
}


def _body(code: str) -> str:
    return (
        f"Tu código de verificación es: {code}\n"
        f"Vence en {settings.OTP_TTL_MINUTES} minutos y solo sirve el último código que te enviamos.\n"
        "Si no fuiste tú, ignora este mensaje."
    )


LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_correo.png"
LOGO_CID = "wispr-logo"

# Colores de WISPR-frontend/style.css (azul, rojo y amarillo del logo).
_BLUE_950, _BLUE_900, _BLUE_800 = "#04122b", "#081a3a", "#0f2c67"
_RED, _YELLOW = "#cd1818", "#f3950d"
_TEXT, _MUTED = "#f5f5f5", "#b5c0d4"


def _html_body(email: str, code: str, purpose: Purpose, logo_src: str | None = f"cid:{LOGO_CID}") -> str:
    """Versión HTML (23 oct), con la estética de la app: fondo azul oscuro,
    el logo arriba, franja roja/amarilla, el código en casillas y la nota de
    seguridad en rojo.

    Reglas de correo HTML (no de página web): tablas y estilos en línea,
    porque Gmail/Outlook ignoran `<style>` y CSS moderno (ni degradados ni
    sombras). El logo va **adjunto dentro del correo** (`cid:`), no como
    enlace a un servidor: así se ve sin pedir "mostrar imágenes" y no depende
    de que la EC2 esté encendida. `logo_src=None` pone el nombre en texto.
    Las casillas son `<span>` pegados sin espacios entre sí: al copiar el
    código sale "123456", sin tabs ni espacios. Un botón "Copiar código" no se
    puede hacer (los correos no ejecutan JavaScript): Gmail lo pone solo al
    detectar un código, y ayuda que vaya en el asunto."""
    digits = "".join(
        '<span style="display:inline-block;width:42px;margin:0 3px;padding:10px 0 8px;'
        f"background:{_BLUE_800};border:1px solid {_YELLOW};border-bottom:3px solid {_YELLOW};border-radius:8px;"
        "font-family:'JetBrains Mono',Consolas,'Courier New',monospace;font-size:28px;font-weight:700;"
        f'color:#ffffff;text-align:center;">{digit}</span>'
        for digit in escape(code)
    )
    if logo_src:
        logo = f'<img src="{escape(logo_src)}" width="180" alt="WISPR" style="display:block;width:180px;max-width:60%;height:auto;border:0;">'
    else:
        logo = f'<span style="font-size:28px;font-weight:800;letter-spacing:3px;color:#ffffff;">WISPR</span>'
    font = "font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
    return f"""\
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>{escape(_subject(code))}</title></head>
<body style="margin:0;padding:0;background:{_BLUE_950};">
<div style="display:none;max-height:0;overflow:hidden;">Tu código de WISPR es {escape(code)}. Vence en {settings.OTP_TTL_MINUTES} minutos.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BLUE_950};">
<tr><td align="center" style="padding:24px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;{font}">
    <tr><td style="background:{_BLUE_800};border-radius:12px 12px 0 0;padding:22px 28px 18px;">
      {logo}
      <div style="margin-top:10px;font:800 11px/1 Consolas,'Courier New',monospace;letter-spacing:2px;color:{_YELLOW};">CAPTURE THE FLAG · VERIFICACIÓN</div>
    </td></tr>
    <tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="72%" style="height:4px;font-size:0;line-height:0;background:{_RED};">&nbsp;</td>
      <td width="28%" style="height:4px;font-size:0;line-height:0;background:{_YELLOW};">&nbsp;</td>
    </tr></table></td></tr>
    <tr><td style="background:{_BLUE_900};border:1px solid {_BLUE_800};border-top:0;border-radius:0 0 12px 12px;padding:26px 28px;font-size:15px;line-height:1.55;color:{_TEXT};">
      <h1 style="margin:0 0 14px;font-size:22px;font-weight:700;color:#ffffff;">Código de verificación</h1>
      <p style="margin:0 0 22px;color:{_TEXT};">{_INTRO[purpose]} el correo <strong style="color:{_YELLOW};">{escape(email)}</strong>. Usa este código para continuar:</p>
      <div style="text-align:center;margin:0 0 22px;white-space:nowrap;">{digits}</div>
      <p style="margin:0 0 20px;text-align:center;font-size:14px;color:{_MUTED};">Vence en <strong style="color:{_YELLOW};">{settings.OTP_TTL_MINUTES} minutos</strong> · solo sirve el último código que te enviamos</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;">
        <tr><td style="background:{_BLUE_950};border-radius:8px;padding:12px 16px;font-size:14px;line-height:1.5;color:{_MUTED};">
          <strong style="color:{_RED};">¿No fuiste tú?</strong> Ignora este mensaje: nadie puede entrar a tu cuenta sin este código. Nunca te lo vamos a pedir por chat ni por teléfono.
        </td></tr>
      </table>
      <p style="margin:0;color:{_TEXT};">Atentamente,<br><strong>El equipo de WISPR</strong></p>
    </td></tr>
    <tr><td style="padding:16px 4px;font-size:12px;line-height:1.5;color:{_MUTED};">Este correo se envió automáticamente; no respondas a esta dirección.<br>WISPR · Plataforma CTF</td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""


@dataclass
class EmailResult:
    ok: bool
    dev: bool = False
    code: str | None = None
    error: str | None = None


def _deliver_dev_code(email: str, code: str, reason: str, purpose: Purpose) -> EmailResult:
    """Modo desarrollo: registra el código en el log y en data/outbox/ (el
    .txt y el .html, que se puede abrir en el navegador para ver el diseño)."""
    logger.warning("[MFA] %s Código para %s: %s", reason, email, code)
    try:
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in ".@-" else "_" for c in email)
        import time

        file_path = OUTBOX_DIR / f"{int(time.time() * 1000)}-{safe_name}.txt"
        file_path.write_text(f"Para: {email}\nAsunto: {_subject(code)}\n\n{_body(code)}\n", encoding="utf-8")
        logo_src = LOGO_PATH.as_uri() if LOGO_PATH.exists() else None
        file_path.with_suffix(".html").write_text(_html_body(email, code, purpose, logo_src), encoding="utf-8")
    except OSError as error:
        logger.error("No se pudo escribir el correo de desarrollo: %s", error)
    return EmailResult(ok=True, dev=True, code=code)


def _fallback(email: str, code: str, reason: str, purpose: Purpose = None) -> EmailResult:
    """
    Qué hacer cuando el correo no se puede enviar de verdad.

    En desarrollo: modo desarrollo (el código va al log y a la respuesta como
    `devCode`). En producción (`ENVIRONMENT=production`) eso anularía el MFA
    — cualquiera vería el código sin tener acceso al correo — así que se
    falla y las rutas responden "No se pudo enviar el correo de
    verificación." Tampoco se escribe el código en el log: en el servidor los
    logs terminan en CloudWatch, y ahí también sería una filtración.
    Pendiente bloqueante #3 de `wispr_terminal_professional/docs/BACKEND-PENDIENTE.md`.
    """
    if settings.ENVIRONMENT == "production":
        logger.error("[MFA] %s No se envió el código a %s (producción: sin modo desarrollo).", reason, email)
        return EmailResult(ok=False, error=reason)
    return _deliver_dev_code(email, code, reason, purpose)


def send_verification_code(email: str, code: str, purpose: Purpose = None) -> EmailResult:
    """
    Envía (o simula) el correo con el código de verificación.

    `purpose` ("register" o "login") solo cambia la primera frase del correo.
    Va en HTML con la versión de texto plano como alternativa, para clientes
    que no muestran HTML.

    Nunca lanza una excepción hacia afuera: si el SMTP real falla, cae al
    modo desarrollo en vez de propagar el error (igual que el prototipo) —
    salvo en producción, ver `_fallback`.
    """
    if not settings.SMTP_HOST:
        return _fallback(email, code, "Sin SMTP configurado.", purpose)

    message = EmailMessage()
    message["Subject"] = _subject(code)
    message["From"] = settings.MAIL_FROM or settings.SMTP_USER
    message["To"] = email
    message.set_content(_body(code))
    logo = LOGO_PATH.read_bytes() if LOGO_PATH.exists() else None
    message.add_alternative(_html_body(email, code, purpose, f"cid:{LOGO_CID}" if logo else None), subtype="html")
    if logo:
        message.get_payload()[1].add_related(logo, maintype="image", subtype="png", cid=f"<{LOGO_CID}>")

    try:
        smtp_class = smtplib.SMTP_SSL if settings.SMTP_SECURE else smtplib.SMTP
        with smtp_class(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if not settings.SMTP_SECURE:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASS or "")
            server.send_message(message)
        return EmailResult(ok=True, dev=False)
    except (smtplib.SMTPException, OSError) as error:
        logger.error("No se pudo enviar el correo de verificación: %s", error)
        return _fallback(email, code, f"Envío SMTP falló ({error}).", purpose)
