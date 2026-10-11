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
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("wispr.email")

OUTBOX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "outbox"

_SUBJECT = "Tu código de verificación WISPR"


def _body(code: str) -> str:
    return (
        f"Tu código de verificación es: {code}\n"
        "Vence en 10 minutos. Si no solicitaste este registro, ignora este mensaje."
    )


@dataclass
class EmailResult:
    ok: bool
    dev: bool = False
    code: str | None = None
    error: str | None = None


def _deliver_dev_code(email: str, code: str, reason: str) -> EmailResult:
    """Modo desarrollo: registra el código en el log y en data/outbox/."""
    logger.warning("[MFA] %s Código para %s: %s", reason, email, code)
    try:
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in ".@-" else "_" for c in email)
        import time

        file_path = OUTBOX_DIR / f"{int(time.time() * 1000)}-{safe_name}.txt"
        file_path.write_text(f"Para: {email}\nAsunto: {_SUBJECT}\n\n{_body(code)}\n", encoding="utf-8")
    except OSError as error:
        logger.error("No se pudo escribir el correo de desarrollo: %s", error)
    return EmailResult(ok=True, dev=True, code=code)


def _fallback(email: str, code: str, reason: str) -> EmailResult:
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
    return _deliver_dev_code(email, code, reason)


def send_verification_code(email: str, code: str) -> EmailResult:
    """
    Envía (o simula) el correo con el código de verificación.

    Nunca lanza una excepción hacia afuera: si el SMTP real falla, cae al
    modo desarrollo en vez de propagar el error (igual que el prototipo) —
    salvo en producción, ver `_fallback`.
    """
    if not settings.SMTP_HOST:
        return _fallback(email, code, "Sin SMTP configurado.")

    message = EmailMessage()
    message["Subject"] = _SUBJECT
    message["From"] = settings.MAIL_FROM or settings.SMTP_USER
    message["To"] = email
    message.set_content(_body(code))

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
        return _fallback(email, code, f"Envío SMTP falló ({error}).")
