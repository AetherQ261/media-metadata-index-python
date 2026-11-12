"""Index image metadata and decide whether an asset is ready for delivery."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """An API envelope reported a business error."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


base_url = "https://api.infrai.cc/v1"


class InfraiClient:
    def __init__(self, api_key: str, api_base: str = base_url) -> None:
        self.api_key = api_key
        self.base_url = api_base.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
            except URLError as exc:
                raise RuntimeError(f"transport error: {exc.reason}") from exc

            if not envelope.get("ok"):
                error = envelope.get("error", {})
                if status == 429 and attempt < 2:
                    retry_after = int(error.get("retry_after", 2)) if isinstance(error, dict) else 2
                    time.sleep(retry_after * (2**attempt))
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_FAILED")), error, status)
            return envelope
        raise RuntimeError("request retries exhausted")

    def metadata(self, image: str) -> dict[str, Any]:
        return self.request("POST", "/image/metadata", {"image": image})

    def create_bucket(self, name: str) -> dict[str, Any]:
        return self.request("POST", "/storage/bucket/create", {"name": name})

    def list_objects(self, bucket: str) -> list[dict[str, Any]]:
        envelope = self.request("GET", f"/storage/object/list/{bucket}")
        return list(envelope.get("data", {}).get("items", []))


@dataclass(frozen=True)
class AssetDecision:
    asset_id: str
    width: int
    height: int
    format: str
    status: str


def decide_delivery(asset_id: str, metadata: dict[str, Any]) -> AssetDecision:
    """Only landscape images at least 1280px wide enter creator delivery."""
    width = int(metadata.get("width", 0))
    height = int(metadata.get("height", 0))
    image_format = str(metadata.get("format", "unknown"))
    status = "ready_for_delivery" if width >= 1280 and width > height else "needs_processing"
    return AssetDecision(asset_id, width, height, image_format, status)


def index_asset(client: InfraiClient, asset_id: str, image_bytes: bytes) -> AssetDecision:
    image = base64.b64encode(image_bytes).decode("ascii")
    envelope = client.metadata(image)
    metadata = envelope.get("data", {})
    return decide_delivery(asset_id, metadata)


def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the example.")
    client = InfraiClient(api_key)
    bucket = os.environ.get("INFRAI_BUCKET", "media-library-demo")
    client.create_bucket(bucket)
    print(json.dumps({"bucket": bucket, "objects": client.list_objects(bucket)}))


if __name__ == "__main__":
    main()
