import json
import os
from typing import Any, Dict, Optional

import requests


class UpstashKV:
    def __init__(self):
        self.url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
        self.token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
        if not self.url or not self.token:
            raise RuntimeError(
                "Missing UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN"
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def set_json(self, key: str, value: Dict[str, Any], ttl_seconds: int = 86400):
        endpoint = f"{self.url}/set/{key}"
        payload = {"value": json.dumps(value, ensure_ascii=False), "ttl": ttl_seconds}
        r = requests.post(endpoint, headers=self._headers(), data=json.dumps(payload))
        r.raise_for_status()
        return r.json()

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        endpoint = f"{self.url}/get/{key}"
        r = requests.get(endpoint, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        result = data.get("result") if isinstance(data, dict) else None
        if result is None:
            return None
        try:
            return json.loads(result)
        except Exception:
            return None
