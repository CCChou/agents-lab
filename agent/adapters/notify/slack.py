import httpx

from agent.adapters.notify.slack_markdown import to_mrkdwn
from agent.domain.job import Notification


class SlackWebhookNotifier:
    """Posts a notification to one channel through a Slack incoming webhook (D-037)."""

    def __init__(self, client: httpx.Client, webhook_url: str) -> None:
        self._client = client
        self._webhook_url = webhook_url

    def send(self, notification: Notification) -> None:
        text = f"*{to_mrkdwn(notification.title)}*\n\n{to_mrkdwn(notification.markdown)}"
        response = self._client.post(self._webhook_url, json={"text": text})
        response.raise_for_status()
