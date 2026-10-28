"""离线整理与检查本目录，不访问网络，不运行第三方源码。"""
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
PAGES = [
    ("official/rules_2027_index.html", "https://bbs.robomaster.com/wiki/20204847/1969149"),
    ("articles/lingbug_2024_rendered.html", "https://bbs.robomaster.com/article/54237"),
    ("articles/dreamchaser_2026_full.html", "https://bbs.robomaster.com/article/1939776"),
]
ONLINE = [
    ("官方规则中心", "https://bbs.robomaster.com/wiki/20204847"),
    ("官方镖头产品说明", "https://www.robomaster.com/en-US/products/components/detail/2675"),
    ("2026区域赛官方反馈答复", "https://bbs.robomaster.com/article/1970800?source=1"),
    ("官方单项赛介绍", "https://www.robomaster.com/zh-CN/robo/rmtc?djifrom=rmu1"),
    ("凌BUG2024公开网盘入口_未登录未下载", "https://pan.baidu.com/s/1dbnmIr5OavHCWws4dsXN0g?pwd=0BUG"),
    ("北理工完整工程入口_未克隆", "https://gitee.com/BITRM2026/dart2026_-open-source"),
    ("北理工2026早期硬件文章_正文抓取超时", "https://bbs.robomaster.com/article/1438280"),
    ("Misaka21仓库_授权待核实", "https://github.com/Misaka21/dart"),
    ("OpenCV_HSV教程", "https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html"),
    ("OpenCV相机模型", "https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html"),
]

def main():
    rows = []
    checks = []
    for relative, url in PAGES:
        path = ROOT / relative
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        content = soup.select_one(".w-e-text-container") or soup.select_one("article") or soup
        text = content.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        target = path.with_suffix(".txt")
        target.write_text(f"来源：{url}\n保存日期：2026-10-26\n说明：文字提取，不含外链图片/视频；版权归原作者。\n\n{text}\n", encoding="utf-8")
        rows.append(dict(title=path.stem, url=url, local_file=relative, status="rendered_html_and_text_saved"))
        markers = {"rules_2027_index": "2026年10月15日", "lingbug_2024_rendered": "发射架视觉", "dreamchaser_2026_full": "296.72"}
        checks.append(dict(check=f"正文标记 {relative}", passed=markers[path.stem] in text))

    manifest = json.loads((ROOT / "download_manifest.json").read_text(encoding="utf-8"))
    for item in manifest:
        path = ROOT / item["file"]
        exists = path.exists()
        rows.append(dict(title=path.name, url=item["url"], local_file=item["file"] if exists else "", status=item["status"]))
        if item["status"] != "failed":
            data = path.read_bytes()
            checks.append(dict(check=f"SHA256 {item['file']}", passed=hashlib.sha256(data).hexdigest() == item["sha256"]))
            checks.append(dict(check=f"字节数 {item['file']}", passed=len(data) == item["bytes"]))
            if path.suffix == ".pdf":
                checks.append(dict(check=f"PDF文件头尾 {item['file']}", passed=data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]))
        else:
            checks.append(dict(check=f"失败请求未写入伪文件 {item['file']}", passed=not exists))

    for title, url in ONLINE:
        rows.append(dict(title=title, url=url, local_file="", status="online_reference_only"))
    with (ROOT / "sources.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["title", "url", "local_file", "status"])
        writer.writeheader()
        writer.writerows(rows)

    # Only self-authored documentation is linted for links; upstream README links depend on its full repo.
    authored = list(ROOT.glob("*.md")) + [ROOT / "code_reference/README.md"]
    for path in authored:
        content = path.read_text(encoding="utf-8")
        checks.append(dict(check=f"UTF8无替换字符 {path.relative_to(ROOT).as_posix()}", passed="\ufffd" not in content))
        for link in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in link or link.startswith("#"):
                continue
            target = path.parent / unquote(link.split("#")[0])
            checks.append(dict(check=f"本地链接 {link}", passed=target.exists()))
    for path in (ROOT / "tools").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        checks.append(dict(check=f"Python语法 {path.name}", passed=True))

    report = dict(
        date="2026-10-26",
        scope="资料包文件完整性；不是功能/命中/计分验证",
        download_success=sum(i["status"] != "failed" for i in manifest),
        download_requests=len(manifest),
        download_failures=[dict(file=i["file"], error=i.get("error", "")) for i in manifest if i["status"] == "failed"],
        checks=checks,
        passed=all(c["passed"] for c in checks),
    )
    (ROOT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = [p for p in ROOT.rglob("*") if p.is_file() and p.name != "collection_files.csv"]
    with (ROOT / "collection_files.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["file", "bytes", "sha256"])
        writer.writeheader()
        for path in sorted(files):
            data = path.read_bytes()
            writer.writerow(dict(file=path.relative_to(ROOT).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    print(json.dumps(dict(passed=report["passed"], checks=len(checks), sources=len(rows), files=len(files) + 1,
                          pdfs=sum(p.suffix == ".pdf" for p in files), total_bytes=sum(p.stat().st_size for p in files),
                          downloads=f"{report['download_success']}/{report['download_requests']}",
                          failures=report["download_failures"]), ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
