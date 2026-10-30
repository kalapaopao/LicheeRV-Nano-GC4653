# Evaluate identical original labeled validation images with the trained YOLO26 .pt.
# All generated files/cache must stay under D:/study/LicheeRV.
import os, json, time, argparse, pathlib, hashlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
for key, val in {
  "YOLO_CONFIG_DIR": str(ROOT/"cache"/"ultralytics"),
  "MPLCONFIGDIR": str(ROOT/"cache"/"matplotlib"),
  "TORCH_HOME": str(ROOT/"cache"/"torch"),
  "XDG_CACHE_HOME": str(ROOT/"cache"),
  "TMP": str(ROOT/"cache"/"tmp"),
  "TEMP": str(ROOT/"cache"/"tmp")
}.items():
    os.environ[key] = val
    pathlib.Path(val).mkdir(parents=True, exist_ok=True)

from ultralytics import YOLO
import torch
BEST = pathlib.Path(r"E:\study\X-AnyLabeling-main\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm\weights\best.pt")
YAML = ROOT/"reports"/"fly_rm_validation.yaml"
DATA = pathlib.Path(r"E:\study\X-AnyLabeling-main\xanylabeling_data\trainer\ultralytics\datasets\detect\fly_rm_20261028_154724")
def digest(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        while True:
            b=f.read(2*1024*1024)
            if not b:break
            h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--sizes",nargs="+",type=int,default=[320,224,640,192])
    args=ap.parse_args()
    dev="0" if torch.cuda.is_available() else "cpu"
    print("ENV_GPU",dev,"TORCH",torch.__version__,flush=True)
    val_images=list((DATA/"images"/"val").iterdir())
    gt=list((DATA/"labels"/"val").glob("*.txt"))
    print("EVAL_SET",len(val_images),"images",len(gt),"labels",flush=True)
    assert len(val_images)==31 and len(gt)==31
    model=YOLO(str(BEST))
    summary=[]
    for size in args.sizes:
        t0=time.monotonic()
        print("EVAL_START",size,flush=True)
        m=model.val(data=str(YAML),imgsz=size,device=dev,batch=1,workers=0,project=str(ROOT/"reports"),name=f"eval_pt_{size}",exist_ok=True,plots=False,save_json=False,verbose=False,rect=False)
        bm=m.box
        result={"size":size,"dataset":str(DATA),"dataset_images":len(val_images),
                "weights":str(BEST),"weights_sha256":digest(BEST),
                "precision":float(bm.mp),"recall":float(bm.mr),
                "map50":float(bm.map50),"map75":float(bm.map75),"map50_95":float(bm.map),
                "speed_ms":dict(m.speed),"wall_seconds":round(time.monotonic()-t0,2),
                "evaluated_on":"PC best.pt FP32/torch (NOT cvimodel FP16)",
                "image_metrics":getattr(bm,"image_metrics",{})}
        with open(ROOT/"reports"/f"eval_pt_{size}.json","w",encoding="utf8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2,default=lambda v:float(v) if hasattr(v,"__float__") else str(v))
        summary.append({k:v for k,v in result.items() if k!="image_metrics"})
        print("EVAL_END",size,"P",round(result["precision"],4),"R",round(result["recall"],4),"MAP50",round(result["map50"],4),"MAP50_95",round(result["map50_95"],4),"SECONDS",result["wall_seconds"],flush=True)
    with open(ROOT/"reports"/"eval_summary.json","w",encoding="utf8") as f:
        json.dump(summary,f,ensure_ascii=False,indent=2)
if __name__=="__main__":main()
