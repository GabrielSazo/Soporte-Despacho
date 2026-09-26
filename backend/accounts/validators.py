import re

from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    def validate(self, password, user=None):
        errors = []
        if len(password or "") < 10:
            errors.append("Debe tener al menos 10 caracteres.")
        if not re.search(r"[A-ZÁÉÍÓÚÜÑ]", password or ""):
            errors.append("Debe incluir al menos una mayúscula.")
        if not re.search(r"[a-záéíóúüñ]", password or ""):
            errors.append("Debe incluir al menos una minúscula.")
        if not re.search(r"[0-9]", password or ""):
            errors.append("Debe incluir al menos un número.")
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "Mínimo 10 caracteres, con mayúscula, minúscula y número."
