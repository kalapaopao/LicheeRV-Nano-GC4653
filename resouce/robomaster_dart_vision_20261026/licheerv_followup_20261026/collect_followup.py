"""仅抓取指定公开网页和 kalapaopao 的公开 Stars；不读凭据、不执行下载工程。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import csv
import json
import os
import re
import time

from bs4 import BeautifulSoup
from curl_cffi import requests
from scrapling.fetchers import StealthyFetcher

ROOT = Path(__file__).resolve().parent
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"D:\AI-Tools\MCP\Scrapling\cache\browsers"
PAGES = [
    ("bit_1438280", "https://bbs.robomaster.com/article/1438280?source=4"),
    ("hero_1884423", "https://bbs.robomaster.com/article/1884423?source=4"),
    ("search_lichee_nano", "https://bbs.robomaster.com/search/Lichee%20nano"),
]

def write_new(name, content):
    path = ROOT / name
    if not path.exists():
        path.write_text(content, encoding="utf-8")

def fetch_page(item):
    stem, url = item
    result = {"kind": "public_bbs", "name": stem, "url": url}
    try:
        path = ROOT / (stem + ".html")
        if path.exists():
            html = path.read_text(encoding="utf-8")
        else:
            response = StealthyFetcher.fetch(url, headless=True, disable_resources=True, timeout=40000, wait=1600)
            result["http_status"] = response.status
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            # markdown sanitization strips scripts and hidden prompt-injection content.
            html = response.html_content
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.select("script, style, noscript"):
                tag.decompose()
            html = str(soup)
            write_new(stem + ".html", html)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.select_one(".w-e-text-container") or soup.select_one("article") or soup
        body_text = body.get_text("\n", strip=True)
        write_new(stem + ".txt", f"来源：{url}\n保存日期：2026-10-26\n仅正文文字；版权归原作者。\n\n{body_text}\n")
        links = [{"text": a.get_text(" ", strip=True), "url": a.get("href")} for a in soup.find_all("a")
                 if a.get("href", "").startswith("https://")]
        media = [{"tag": x.name, "url": x.get("src") or x.get("data-src")} for x in body.find_all(["img", "video", "source"])
                 if x.get("src") or x.get("data-src")]
        write_new(stem + "_links.json", json.dumps({"source": url, "links": links, "media": media}, ensure_ascii=False, indent=2))
        result.update(status="saved", text_chars=len(body_text), sha256=sha256(html.encode()).hexdigest(),
                      snippets=[body_text[max(0,m.start()-180):m.end()+450] for m in list(re.finditer(r"GC4653|CG4653|fps|FPS|帧率|github|识别设计",body_text))[:18]])
    except Exception as exc:
        result.update(status="failed", error=str(exc))
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

def collect_stars():
    records, pages = [], []
    for page in range(1, 11):
        url = f"https://api.github.com/users/kalapaopao/starred?per_page=100&page={page}"
        filename = f"github_stars_page_{page:02d}.json"
        try:
            path = ROOT / filename
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                response = requests.get(url, headers={"Accept":"application/vnd.github+json", "User-Agent":"LicheeRV-research"}, impersonate="chrome", timeout=65)
                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}")
                data = response.json()
                if not isinstance(data, list):
                    raise RuntimeError("expected repository list")
                write_new(filename, json.dumps(data, ensure_ascii=False, indent=2))
            records.extend(data)
            pages.append({"url":url,"status":"saved","count":len(data),"file":filename})
            if len(data) < 100:
                break
            time.sleep(0.4)
        except Exception as exc:
            pages.append({"url":url,"status":"failed","error":str(exc)})
            break
    selected=[]
    terms = ["dart", "飞镖", "lichee", "sg200", "gc4653", "maix", "cvi", "robomaster", "rm_vision", "opencv", "yolo"]
    for r in records:
        summary = " ".join([r.get("full_name") or "",r.get("description") or ""," ".join(r.get("topics") or [])]).lower()
        matched = [t for t in terms if t in summary]
        if matched:
            selected.append({"repo":r["full_name"],"url":r["html_url"],"description":r.get("description"),"matched":matched,"default_branch":r.get("default_branch"),"license":(r.get("license") or {}).get("spdx_id")})
    write_new("github_stars_candidates.json", json.dumps(selected, ensure_ascii=False, indent=2))
    with (ROOT / "github_stars_index.csv").open("w",encoding="utf-8-sig",newline="") as output:
        writer=csv.DictWriter(output,fieldnames=["repo","url","description","topics","language"])
        writer.writeheader()
        for r in records:
            writer.writerow({"repo":r["full_name"],"url":r["html_url"],"description":r.get("description"),"topics":";".join(r.get("topics") or []),"language":r.get("language")})
    result={"kind":"public_github_stars","username":"kalapaopao","total_read":len(records),"pagination_complete":bool(pages and pages[-1].get("count",100)<100),"pages":pages,"candidates":selected}
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        stars=pool.submit(collect_stars)
        results=[fetch_page(item) for item in PAGES]
        results.append(stars.result())
    report={"retrieved_utc":datetime.now(timezone.utc).isoformat(),"results":results}
    (ROOT / "collection_log.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
