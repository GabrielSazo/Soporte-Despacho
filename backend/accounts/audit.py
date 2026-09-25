def audit(actor, action, entidad="", entidad_id="", detalle="", request=None):
    try:
        from .models import AuditLog

        ip = ""
        if request is not None:
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
            ip = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", ""))[:45]
        AuditLog.objects.create(
            actor=actor if getattr(actor, "pk", None) else None,
            action=action,
            entidad=entidad or "",
            entidad_id=str(entidad_id or ""),
            detalle=detalle or "",
            ip=ip,
        )
    except Exception:
        pass
