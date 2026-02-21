import requests
import json
import os
import traceback
from datetime import datetime

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str):
        if not self.webhook_url:
            return
        payload = {"text": message}
        try:
            requests.post(self.webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=10)
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")

# Usage:
# notifier = SlackNotifier(os.environ.get("SLACK_WEBHOOK_URL"))
# notifier.send("ETL failed!")
