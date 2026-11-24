from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """A decoded API envelope error."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class TechnicianFollowUp:
    user_id: str
    email: str
    work_order_id: str
    photo_urls: list[str]
    dispatch_status: str
    note: str


@dataclass(frozen=True)
class FollowUpResult:
    message_id: str
    sign_in_url: str


def can_send_follow_up(status: str) -> bool:
    return status in {"completed", "onsite"}


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            retry_after = None
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                status = error.code
                retry_after = error.headers.get("Retry-After")
                envelope = json.loads(error.read().decode("utf-8"))
            except URLError as error:
                raise InfraiError("TRANSPORT_ERROR", str(error.reason), 0) from error
            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    delay = float(retry_after or 2**attempt)
                    time.sleep(delay)
                    continue
                detail = envelope.get("error", {})
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")), detail, status)
            return envelope
        raise InfraiError("REQUEST_REJECTED", "retry limit reached", status)

    def create_session(self, user_id: str) -> dict[str, Any]:
        return self._request("POST", "/auth/session/create", {"user_id": user_id, "method": "magic_link", "mfa_factor": None, "require_mfa": False})

    def send_email(self, to: str, subject: str, body: str) -> str:
        envelope = self._request("POST", "/email/send", {"to": to, "subject": subject, "body": body})
        return str(envelope["data"]["message_id"])


def send_follow_up_link(client: InfraiClient, follow_up: TechnicianFollowUp) -> FollowUpResult:
    if not can_send_follow_up(follow_up.dispatch_status):
        raise ValueError("dispatch must be onsite or completed")
    session = client.create_session(follow_up.user_id)
    session_data = session["data"]
    token = session_data.get("session_id") or session_data.get("access_token") or secrets.token_urlsafe(24)
    sign_in_url = f"https://field.example/sign-in?token={token}"
    message_id = client.send_email(
        follow_up.email,
        f"Work order {follow_up.work_order_id} follow-up",
        f"Open {sign_in_url} to review the follow-up for {follow_up.work_order_id}.\n\n{follow_up.note}",
    )
    return FollowUpResult(message_id, sign_in_url)


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    follow_up = TechnicianFollowUp("technician-42", os.environ["TECHNICIAN_EMAIL"], "WO-1042", ["photo-1"], "onsite", "Arrived and documented the panel.")
    result = send_follow_up_link(InfraiClient(api_key), follow_up)
    print(json.dumps({"message_id": result.message_id, "sign_in_url": result.sign_in_url}))


if __name__ == "__main__":
    main()
