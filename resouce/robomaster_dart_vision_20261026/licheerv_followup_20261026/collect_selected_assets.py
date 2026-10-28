"""下载少量与本次研究直接相关的公开文件，不解压、不运行工程。"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
from urllib.parse import unquote
from zipfile import ZipFile, is_zipfile

from curl_cffi import requests

ROOT=Path(__file__).resolve().parent
SOURCES=[]
stars=json.loads((ROOT/'github_stars_page_01.json').read_text(encoding='utf-8'))
repos=['gaowanlu/RMDartsVision','FaterYU/rm_auto_aim','PraySky1337/AT_NN_Detector','qwq9966qwq/ITL_Hero_Shoot','rerun-io/rerun','CVHub520/X-AnyLabeling']
for name in repos:
    info=next(r for r in stars if r['full_name']==name)
    prefix='github_reference/'+name.replace('/','__')
    SOURCES.append((prefix+'/README.md',f"https://raw.githubusercontent.com/{name}/{info['default_branch']}/README.md"))
    if name=='rerun-io/rerun':
        for license_name in ['LICENSE-APACHE','LICENSE-MIT']:
            SOURCES.append((prefix+'/'+license_name,f"https://raw.githubusercontent.com/{name}/{info['default_branch']}/{license_name}"))
    elif info.get('license'):
        SOURCES.append((prefix+'/LICENSE',f"https://raw.githubusercontent.com/{name}/{info['default_branch']}/LICENSE"))
SOURCES += [
    ('github_reference/gaowanlu__RMDartsVision/GreenSpot.cpp','https://raw.githubusercontent.com/gaowanlu/RMDartsVision/master/src/GreenSpot/GreenSpot.cpp'),
    ('github_reference/gaowanlu__RMDartsVision/GreenSpot.h','https://raw.githubusercontent.com/gaowanlu/RMDartsVision/master/src/GreenSpot/GreenSpot.h'),
    ('github_reference/FaterYU__rm_auto_aim/armor_detector_README.md','https://raw.githubusercontent.com/FaterYU/rm_auto_aim/main/armor_detector/README.md'),
    ('github_reference/kid-king-x__DartGuide2025-Helios/README.md','https://raw.githubusercontent.com/kid-king-x/DartGuide2025-Helios/main/README.md'),
    ('github_reference/kid-king-x__DartGuide2025-Helios/LICENSE.txt','https://raw.githubusercontent.com/kid-king-x/DartGuide2025-Helios/main/LICENSE.txt'),
    ('github_reference/kid-king-x__DartGuide2025-Helios/maixcdk_development.md','https://raw.githubusercontent.com/kid-king-x/DartGuide2025-Helios/main/Software/maixcdk%E7%9A%84%E5%BC%80%E5%8F%91/maixcdk%E7%9A%84%E5%BC%80%E5%8F%91.md'),
]
hero=json.loads((ROOT/'hero_1884423_links.json').read_text(encoding='utf-8'))
for link in hero['links']:
    if link['url'].endswith('.zip'):
        SOURCES.append(('attachments/'+unquote(link['url'].split('/')[-1]),link['url']))
for media in hero['media']:
    if media['url'].endswith('/yuque_diagram.jpg'):
        SOURCES.append(('attachments/HERO_vision_pipeline.jpg',media['url']))

def fetch(item):
    filename,url=item
    dest=(ROOT/filename).resolve()
    assert ROOT in dest.parents
    result={'file':filename,'url':url}
    try:
        if dest.exists():
            data=dest.read_bytes()
            result['status']='existing_not_overwritten'
        else:
            error=None
            for _ in range(2):
                try:
                    response=requests.get(url,impersonate='chrome',timeout=100)
                    result['http_status']=response.status_code
                    if response.status_code!=200:
                        raise RuntimeError(f'HTTP {response.status_code}')
                    data=response.content
                    if len(data)>20_000_000:
                        raise RuntimeError('exceeds 20 MB per-file limit')
                    if not data:
                        raise RuntimeError('empty response')
                    if dest.suffix in {'.md','.cpp','.h'}:
                        data.decode('utf-8')
                        if b'<!DOCTYPE html' in data[:300]:
                            raise RuntimeError('unexpected HTML')
                    if dest.suffix=='.zip' and not is_zipfile(BytesIO(data)):
                        raise RuntimeError('not a ZIP file')
                    break
                except Exception as exc:
                    error=exc
            else:
                raise error
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as output:
                output.write(data)
            result['status']='downloaded'
        result.update(bytes=len(data),sha256=sha256(data).hexdigest())
        if dest.suffix=='.zip':
            with ZipFile(BytesIO(data)) as archive:
                # Directory metadata only: no extraction, scripts, or embedded sensitive files are read.
                entries=[{'name':x.filename,'bytes':x.file_size,'compressed_bytes':x.compress_size} for x in archive.infolist()]
            listing=dest.with_suffix('.listing.json')
            listing.write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
            result['archive_entries']=len(entries)
    except Exception as exc:
        result.update(status='failed',error=str(exc))
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    previous=ROOT/'selected_assets_manifest.json'
    history=ROOT/'selected_assets_attempts.jsonl'
    if previous.exists() and not history.exists():
        history.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in json.loads(previous.read_text(encoding='utf-8'))),encoding='utf-8')
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(fetch,SOURCES))
    with history.open('a',encoding='utf-8') as output:
        for item in results:
            output.write(json.dumps(item,ensure_ascii=False)+'\n')
    (ROOT/'selected_assets_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
