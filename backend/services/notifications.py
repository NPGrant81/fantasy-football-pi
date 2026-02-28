from typing import Dict, Any


class NotifyService:
    """Thin wrapper around whatever email/notification backend is configured.

    In production this would interface with Mailgun/SES/SendGrid etc.; the
    tests simply stub or monkeypatch it as needed.
    """

    @staticmethod
    def send_transactional_email(user_id: int, template_id: str, context: Dict[str, Any]):
        # placeholder implementation - in real life this would enqueue a task or
        # call an external API.  For now we just log to console for visibility.
        print(f"[Notify] user={user_id} template={template_id} context={context}")
