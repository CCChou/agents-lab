import json

import httpx
import pytest

from agent.adapters.notify.slack import SlackWebhookNotifier
from agent.domain.interfaces import Notifier
from agent.domain.job import Notification

WEBHOOK = "https://hooks.slack.test/services/T/B/X"


def make_notifier(handler) -> SlackWebhookNotifier:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SlackWebhookNotifier(client, WEBHOOK)


def test_satisfies_notifier_port():
    assert isinstance(make_notifier(lambda r: httpx.Response(200)), Notifier)


def test_send_posts_the_title_and_converted_markdown_to_the_webhook():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    make_notifier(handler).send(Notification("每日摘要", "## 議題\n**重點**", session_id="s1"))

    assert str(seen[0].url) == WEBHOOK
    assert json.loads(seen[0].content) == {"text": "*每日摘要*\n\n*議題*\n*重點*"}


def test_send_raises_when_slack_rejects_the_message():
    notifier = make_notifier(lambda r: httpx.Response(404, text="no_service"))

    with pytest.raises(httpx.HTTPStatusError):
        notifier.send(Notification("t", "m", session_id="s1"))
