# preview_server.py
# 경로 꼬임을 "구조적으로" 제거:
# - 프로젝트 루트 고정 서빙
# - /_open/<filename> 로 파일명을 주면 프로젝트 전체에서 찾아서 자동으로 열어줌
# - /_find?name=xxx 로 매칭 경로 목록 확인 가능

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import List

from flask import Flask, abort, redirect, request, send_from_directory
from flask_cors import CORS

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)
CORS(app)


def safe_join(rel: str) -> Path:
    rel = rel.lstrip("/")
    target = (PROJECT_ROOT / rel).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        raise PermissionError("Path traversal blocked")
    return target


def find_by_name(filename: str) -> List[Path]:
    """
    프로젝트 전체에서 filename과 정확히 일치하는 파일을 찾는다.
    """
    matches: List[Path] = []
    for p in PROJECT_ROOT.rglob(filename):
        if p.is_file() and p.name.lower() == filename.lower():
            matches.append(p)
    return matches


@app.route("/")
def root():
    return redirect("/_list")


@app.route("/_list")
def list_page():
    """
    루트 확인 페이지 + '자주 찾는 파일' 자동 링크 제공
    """
    html = []
    html.append("<h2>Preview Server Root</h2>")
    html.append(f"<p>PROJECT_ROOT = {PROJECT_ROOT}</p>")

    # 핵심 폴더 존재 여부
    for f in ["templates", "outputs", "backend"]:
        p = PROJECT_ROOT / f
        if p.exists():
            html.append(f'✅ <a href="/{f}/">{f}/</a><br/>')
        else:
            html.append(f"❌ {f}/ (not found)<br/>")

    html.append("<hr/>")
    html.append("<h3>Auto Open (path-independent)</h3>")
    html.append("<ul>")
    html.append(
        '<li><a href="/_open/web3_checkout.html">/_open/web3_checkout.html</a></li>'
    )
    html.append(
        '<li><a href="/_open/index.html">/_open/index.html</a> (여러 개면 목록 표시)</li>'
    )
    html.append("</ul>")

    html.append("<h3>Find</h3>")
    html.append(
        '<p>예: <a href="/_find?name=web3_checkout.html">/_find?name=web3_checkout.html</a></p>'
    )

    return "\n".join(html)


@app.route("/_find")
def find_page():
    """
    파일명으로 매칭 리스트를 보여준다.
    """
    name = (request.args.get("name") or "").strip()
    if not name:
        return "name query is required. ex) /_find?name=web3_checkout.html", 400

    matches = find_by_name(name)
    if not matches:
        return f"<h3>Not found: {name}</h3>", 404

    html = [f"<h3>Found: {name}</h3>", "<ul>"]
    for p in matches:
        rel = p.relative_to(PROJECT_ROOT).as_posix()
        html.append(f'<li><a href="/{rel}">/{rel}</a></li>')
    html.append("</ul>")
    html.append('<p><a href="/_list">Back</a></p>')
    return "\n".join(html)


@app.route("/_open/<path:filename>")
def open_by_name(filename: str):
    """
    filename만으로 프로젝트 전체에서 찾아 첫 번째 매칭을 열어준다.
    여러 개면 /_find로 유도한다.
    """
    matches = find_by_name(filename)
    if not matches:
        abort(404)

    if len(matches) > 1:
        # 동일 파일명 여러 개면 목록 페이지로 보냄
        return redirect(f"/_find?name={filename}")

    target = matches[0]
    rel = target.relative_to(PROJECT_ROOT).as_posix()
    return redirect(f"/{rel}")


@app.route("/<path:relpath>")
def serve_any(relpath: str):
    """
    프로젝트 루트 하위 모든 파일/폴더 서빙
    """
    try:
        target = safe_join(relpath)
    except PermissionError:
        abort(403)

    if target.is_dir():
        entries = []
        for child in sorted(target.iterdir()):
            name = child.name + ("/" if child.is_dir() else "")
            url = f"/{relpath.rstrip('/')}/{name}"
            entries.append(f'<li><a href="{url}">{name}</a></li>')
        return "\n".join(
            [
                f"<h3>Directory: /{relpath}/</h3>",
                "<ul>",
                *entries,
                "</ul>",
                '<p><a href="/_list">Back</a></p>',
            ]
        )

    if not target.exists():
        abort(404)

    mimetypes.init()
    return send_from_directory(str(target.parent), target.name, as_attachment=False)


def main() -> None:
    host = "127.0.0.1"
    port = 8088
    print(f"[PREVIEW] PROJECT_ROOT = {PROJECT_ROOT}")
    print(f"[PREVIEW] http://{host}:{port}/_list")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
