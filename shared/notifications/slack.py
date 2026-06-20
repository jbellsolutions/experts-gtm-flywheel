from __future__ import annotations

import httpx
import os


CHANNEL_MAP = {
    "ops": "#agent-ops",
    "pipeline": "#pipeline",
    "intel": "#intel",
    "content": "#content",
    "finance": "#finance",
}


class SlackNotifier:
    def __init__(self) -> None:
        self.token = os.getenv("SLACK_BOT_TOKEN", "")
        # User (xoxp) token. A bot can only post to channels it's been added
        # to (private channels return channel_not_found otherwise). The user
        # token can post to any channel the authed user is a member of, which
        # removes the manual /invite step for channel-routed deployments
        # (e.g. Tony's brief -> SLACK_CHANNEL_OVERRIDE). Used only as a
        # fallback when the bot post fails with a membership error.
        self.user_token = os.getenv("SLACK_USER_TOKEN", "")
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
        self._override = os.getenv("SLACK_CHANNEL_OVERRIDE")

    def _resolve_channel(self, channel: str) -> str:
        if self._override:
            return self._override
        return CHANNEL_MAP.get(channel, channel)

    async def _post(self, payload: dict) -> dict:
        """POST chat.postMessage; on a bot membership error fall back to the
        user token. Returns the final Slack API response dict."""
        membership_errors = {"channel_not_found", "not_in_channel"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
            )
            data = r.json()
            if data.get("ok"):
                return data
            err = data.get("error", "")
            # Fall back to the user token for channel membership failures.
            if err in membership_errors and self.user_token:
                r2 = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.user_token}"},
                    json=payload,
                )
                d2 = r2.json()
                if not d2.get("ok"):
                    print(f"[slack] post failed (bot:{err}, "
                          f"user:{d2.get('error')}) channel={payload.get('channel')}")
                return d2
            if not data.get("ok"):
                print(f"[slack] post failed ({err}) channel={payload.get('channel')}")
            return data

    async def send(
        self,
        channel: str,
        message: str,
        agent_id: str,
        priority: str = "normal",
        blocks: list | None = None,
    ) -> None:
        resolved = self._resolve_channel(channel)
        payload: dict = {
            "channel": resolved,
            "text": f"[{agent_id}] {message}",
        }
        if blocks:
            payload["blocks"] = blocks
        await self._post(payload)

    async def send_approval_request(
        self,
        channel: str,
        action: str,
        context: dict,
        callback_id: str,
    ) -> None:
        """Send an interactive approval request with Approve/Reject buttons."""
        resolved = self._resolve_channel(channel)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Approval needed:* {action}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*{k}:*\n{v}"}
                for k, v in context.items()
            ]},
            {"type": "actions", "block_id": callback_id, "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"},
                 "style": "primary", "value": "approve"},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject"},
                 "style": "danger", "value": "reject"},
            ]},
        ]
        await self._post({"channel": resolved, "blocks": blocks})
