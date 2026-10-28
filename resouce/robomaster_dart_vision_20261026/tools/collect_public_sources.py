"""仅下载明确列出的公开资料；不安装依赖、不执行下载内容、不读取 Git。

使用 D:\\AI-Tools\\MCP\\Scrapling\\venv\\Scripts\\python.exe 运行。
输出仅限本脚本上两级的资料目录。已有成功文件只校验，不覆盖。
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from urllib.parse import unquote

from bs4 import BeautifulSoup
from curl_cffi import requests

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ("official/rules_2026_v1.4.0.pdf", "https://bbs-web-static.robomaster.com/38afa6d7914345f7bb5d496692fd429b1773977681621/RoboMaster%202026%20%E6%9C%BA%E7%94%B2%E5%A4%A7%E5%B8%88%E8%B6%85%E7%BA%A7%E5%AF%B9%E6%8A%97%E8%B5%9B%E6%AF%94%E8%B5%9B%E8%A7%84%E5%88%99%E6%89%8B%E5%86%8CV1.4.0%EF%BC%8820260320%EF%BC%89.pdf"),
    ("official/dart_trigger_manual_zh_2020.pdf", "https://rm-static.djicdn.com/tem/43259/RoboMaster%E9%A3%9E%E9%95%96%E8%A7%A6%E5%8F%91%E8%A3%85%E7%BD%AE%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C.pdf"),
    ("articles/team_report_2025_53pages.pdf", "https://bbs-web-static.robomaster.com/1ab1aff78637442c9e48f72def0cfff61756961976052/%E9%A3%9E%E9%95%96%E6%8A%80%E6%9C%AF%E6%8A%A5%E5%91%8A.pdf"),
    ("code_reference/misaka21_README.md", "https://raw.githubusercontent.com/Misaka21/dart/main/README.md"),
    ("code_reference/misaka21_detector.cpp", "https://raw.githubusercontent.com/Misaka21/dart/main/detector/detector.cpp"),
    ("code_reference/misaka21_param.toml", "https://raw.githubusercontent.com/Misaka21/dart/main/config/param.toml"),
    ("code_reference/misaka21_LICENSE", "https://raw.githubusercontent.com/Misaka21/dart/main/LICENSE"),
]

def download(item):
    relative, url = item
    target = (ROOT / relative).resolve()
    assert ROOT in target.parents
    result = {"file": relative, "url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat()}
    try:
        if target.exists():
            data = target.read_bytes()
            result["status"] = "existing_not_overwritten"
        else:
            response = requests.get(url, impersonate="chrome", timeout=240)
            result["http_status"] = response.status_code
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}")
            data = response.content
            if not data:
                raise RuntimeError("empty response")
            if target.suffix.lower() == ".pdf" and not data.startswith(b"%PDF-"):
                raise RuntimeError("response is not a PDF")
            if target.suffix.lower() in {".cpp", ".toml", ".md"} and b"<!DOCTYPE html" in data[:300]:
                raise RuntimeError("unexpected HTML instead of source")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(data)
            result["status"] = "downloaded"
        result.update(bytes=len(data), sha256=sha256(data).hexdigest())
    except Exception as exc:
        result.update(status="failed", error=str(exc))
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

def attachment_urls(relative):
    path = ROOT / relative
    if not path.exists():
        return []
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    return list(dict.fromkeys(a.get("href", "") for a in soup.find_all("a")
                             if a.get("href", "").startswith("https://") and ".pdf" in a.get("href", "")))

def main():
    for url in attachment_urls("official/rules_2027_index.html"):
        name = unquote(url.split("/")[-1])
        if "20261015" in name and "比赛规则" in name:
            SOURCES.append(("official/rules_2027_v1.0.0.pdf", url))
        elif "20261015" in name and "制作规范" in name:
            SOURCES.append(("official/robot_spec_2027_v1.0.0.pdf", url))
    for url in attachment_urls("articles/dreamchaser_2026_full.html"):
        if unquote(url.split("/")[-1]) == "技术报告.pdf":
            SOURCES.append(("articles/dreamchaser_2026_technical_report.pdf", url))
    manifest = ROOT / "download_manifest.json"
    history = ROOT / "download_attempts.jsonl"
    if manifest.exists() and not history.exists():
        with history.open("x", encoding="utf-8") as output:
            for entry in json.loads(manifest.read_text(encoding="utf-8")):
                output.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # A missing license is recorded, not guessed; do not repeatedly request a known 404.
    previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    known_404 = {r["file"]: r for r in previous if r.get("http_status") == 404}
    requested = [item for item in SOURCES if item[0] not in known_404]
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(download, requested))
    with history.open("a", encoding="utf-8") as output:
        for entry in results:
            output.write(json.dumps(entry, ensure_ascii=False) + "\n")
    results.extend(known_404.values())
    # Only this generated manifest is refreshed on reruns; downloaded material is not overwritten.
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Downloaded/existing: {sum(r['status'] != 'failed' for r in results)}/{len(results)}")

if __name__ == "__main__":
    main()
