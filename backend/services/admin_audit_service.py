import importlib

from sqlalchemy.orm import Session

models = importlib.import_module("backend.models")


def record_privileged_action(
    db: Session,
    actor,
    action: str,
    scope: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    league_id: int | None = None,
    metadata_json: dict | None = None,
) -> None:
    entry = models.AdminAuditLog(
        actor_user_id=getattr(actor, "id", None),
        actor_username=getattr(actor, "username", "unknown"),
        actor_is_superuser=bool(getattr(actor, "is_superuser", False)),
        actor_is_commissioner=bool(getattr(actor, "is_commissioner", False)),
        action=action,
        scope=scope,
        target_type=target_type,
        target_id=target_id,
        league_id=league_id,
        metadata_json=metadata_json or {},
    )
    db.add(entry)
    db.commit()