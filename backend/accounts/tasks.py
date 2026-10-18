"""Tareas en segundo plano de accounts (Celery)."""
from django.conf import settings
from django.core.mail import send_mail

from celery import shared_task


@shared_task
def send_password_reset_email(user_id, reset_link):
    """Envía el correo de restablecimiento de contraseña.

    Corre en Celery (y de forma sincrónica solo como respaldo si no hay
    broker) para que la respuesta de la API no delate —por el tiempo—
    si la cuenta existe o no: RF-004, sin enumerar usuarios.
    """
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    if not user.is_active:
        return

    subject = "Soporte Despacho Tigo - Restablece tu contraseña"
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; background: #f3f6ff; border-radius: 12px;">
      <h2 style="color: #001eb4; margin: 0 0 12px;">Hola {user.display_name},</h2>
      <p style="color: #0f1a4a; font-size: 14px; line-height: 1.6;">Recibimos una solicitud para restablecer tu contraseña en <b>Soporte Despacho Tigo</b>.</p>
      <p style="text-align: center; margin: 28px 0;">
        <a href="{reset_link}" style="display: inline-block; padding: 12px 28px; background: #001eb4; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">Restablecer contraseña</a>
      </p>
      <p style="color: #5a658d; font-size: 12px;">Este botón es válido por 1 hora. Si no solicitaste este cambio, ignora este correo.</p>
      <p style="color: #8d97b5; font-size: 11px; word-break: break-all;">Si el botón no funciona, copia este enlace: {reset_link}</p>
    </div>
    """
    message = f"Hola {user.display_name},\n\nRestablece tu contraseña aquí: {reset_link}\n\nVálido por 1 hora."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False, html_message=html_message)
