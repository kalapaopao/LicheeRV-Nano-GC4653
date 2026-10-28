"""离线校验研究包，不访问网络，不执行上游源码或模型。"""
import ast
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parent

def main():
    checks=[]
    def check(name,result):
        checks.append({'check':name,'passed':bool(result)})
    manifest=json.loads((ROOT/'selected_assets_manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        path=ROOT/item['file']
        check('文件成功 '+item['file'],item['status']!='failed' and path.exists())
        if not path.exists():
            continue
        data=path.read_bytes()
        check('SHA256 '+item['file'],sha256(data).hexdigest()==item['sha256'])
        check('字节数 '+item['file'],len(data)==item['bytes'])
        if path.suffix=='.zip':
            with ZipFile(path) as z:
                check('ZIP CRC '+path.name,z.testzip() is None)
                check('PCB而非模型 '+path.name,all(Path(n).suffix.lower() in {'.schdoc','.prjpcb','.pcbdoc'} for n in z.namelist()))
    stars=json.loads((ROOT/'github_stars_page_01.json').read_text(encoding='utf-8'))
    log=json.loads((ROOT/'collection_log.json').read_text(encoding='utf-8'))
    result=next(x for x in log['results'] if x['kind']=='public_github_stars')
    check('Stars分页完成',result['pagination_complete'] and result['total_read']==len(stars)==75)
    for stem in ['bit_1438280','hero_1884423','search_lichee_nano']:
        text=(ROOT/(stem+'.txt')).read_text(encoding='utf-8')
        check('正文非空 '+stem,len(text)>2000)
    bit=(ROOT/'bit_1438280.txt').read_text(encoding='utf-8')
    check('BIT同硬件60FPS证据','LicheeRV Nano+GC4653' in bit and '1280*720 60fps' in bit)
    hero=(ROOT/'hero_1884423.txt').read_text(encoding='utf-8')
    check('HERO文字未给数值FPS','fps' not in hero.lower())
    image_header=(ROOT/'attachments/HERO_vision_pipeline.jpg').read_bytes()[:12]
    check('HERO原始流程图存在',image_header.startswith(b'\xff\xd8\xff') or image_header.startswith(b'\x89PNG\r\n\x1a\n') or (image_header.startswith(b'RIFF') and image_header[8:12]==b'WEBP'))
    for path in ROOT.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'),filename=path.name)
        check('脚本语法 '+path.name,True)
    for path in ROOT.glob('*.md'):
        content=path.read_text(encoding='utf-8')
        check('文档UTF8 '+path.name,'\ufffd' not in content)
        for link in re.findall(r'\]\(([^)]+)\)',content):
            if '://' not in link and not link.startswith('#'):
                check('本地链接 '+link,(path.parent/link.split('#')[0]).exists())
    report={'scope':'资料完整性，不是模型性能或稳定性','public_stars':len(stars),'asset_count':len(manifest),'checks':checks,'passed':all(x['passed'] for x in checks),'model_weights_obtained':False,'board_deployment_performed':False}
    (ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=sorted(x for x in ROOT.rglob('*') if x.is_file() and x.name!='files.csv')
    with (ROOT/'files.csv').open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=['file','bytes','sha256'])
        writer.writeheader()
        for path in files:
            data=path.read_bytes()
            writer.writerow({'file':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha256(data).hexdigest()})
    print(json.dumps({'passed':report['passed'],'checks':len(checks),'files':len(files)+1,'asset_count':len(manifest),'bytes_excluding_inventory':sum(x.stat().st_size for x in files),'failed_checks':[x for x in checks if not x['passed']]},ensure_ascii=False,indent=2))
    if not report['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
