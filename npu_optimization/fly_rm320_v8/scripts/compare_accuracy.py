# Fair measurement on the SAME images per row; disclose cross-split training leakage.
import os,pathlib,time,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
for k,v in {"YOLO_CONFIG_DIR":"cache/ultralytics","MPLCONFIGDIR":"cache/matplotlib","TORCH_HOME":"cache/torch","XDG_CACHE_HOME":"cache","TEMP":"cache/tmp","TMP":"cache/tmp"}.items():
    os.environ[k]=str(ROOT/v);(ROOT/v).mkdir(parents=True,exist_ok=True)
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
os.environ["OMP_NUM_THREADS"]="2"
os.environ["MKL_NUM_THREADS"]="2"
from ultralytics import YOLO
import torch
torch.set_num_threads(2)
V26=ROOT.parent/"fly_rm320"/"models"/"best.pt"
V8=ROOT/"models"/"best.pt"
SETS={
"v26_val":ROOT.parent/"fly_rm320"/"eval"/"new"/"data.yaml",
"v8_val":ROOT/"eval"/"v8"/"data.yaml",
}
assert V26.exists() and V8.exists()
for y in SETS.values():assert y.exists(),y
results=[]
for ds,yaml in SETS.items():
  for modelname,weight in [("YOLO26n",V26),("YOLOv8n",V8)]:
    print("START",ds,modelname,flush=True)
    t=time.monotonic()
    model=YOLO(str(weight))
    m=model.val(data=str(yaml),imgsz=320,batch=1,device="cpu",workers=0,project=str(ROOT/"reports"),name=f"eval_{ds}_{modelname}",exist_ok=True,plots=False,save_json=False,verbose=False,rect=False)
    row={"dataset":ds,"model":modelname,"size":320,"precision":float(m.box.mp),"recall":float(m.box.mr),"mAP50":float(m.box.map50),"mAP50_95":float(m.box.map),"wall_s":round(time.monotonic()-t,2)}
    results.append(row)
    (ROOT/"reports"/"comparison.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf8")
    print("RESULT",json.dumps(row),flush=True)
