# deploy_module_vercel_api.py
# 목적: Vercel CLI 없이, Vercel REST API로 정적 사이트(HTML/CSS/JS)를 배포한다.

import base64
import json
import os
from typing import Dict, List, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()


def _get_headers() -> Dict[str, str]:
    token = os.getenv("VERCEL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("VERCEL_TOKEN이 .env에 없습니다.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _team_qs() -> str:
    team_id = os.getenv("VERCEL_TEAM_ID", "").strip()
    if team_id:
        return f"?teamId={team_id}"
    return ""


def deploy_static_files(
    project_name: str,
    files: List[Tuple[str, bytes]],
    production: bool = True,
) -> str:
#     """
#     Vercel Deployments API로 파일 목록을 올려 배포 URL을 반환한다.
#     files: [("index.html", b"..."), ("assets/app.js", b"..."), ...]
#     """
    headers = _get_headers()
    qs = _team_qs()

    # Vercel에 올릴 파일 포맷으로 변환
    vercel_files = []
    for path, content in files:
        vercel_files.append(
            {
                "file": path,
                "data": base64.b64encode(content).decode("utf-8"),
                "encoding": "base64",
            }
        )

    payload = {
        "name": project_name,
        "files": vercel_files,
        "projectSettings": {"framework": None},
        "target": "production" if production else "preview",
    }

    url = f"https://api.vercel.com/v13/deployments{qs}"
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code >= 300:
        raise RuntimeError(f"Vercel 배포 실패: {r.status_code}\n{r.text}")

    data = r.json()
    # 배포 결과 URL
    # 예: https://xxxxx.vercel.app
    deployment_url = data.get("url", "")
    if not deployment_url:
        raise RuntimeError(
            "Vercel 응답에서 url을 찾지 못했습니다:\n"
            + json.dumps(data, ensure_ascii=False)
        )

    return "https://" + deployment_url
