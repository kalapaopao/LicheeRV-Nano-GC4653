# Small unbiased cross-training sample (3 shared validation images).
import os, pathlib, json
R=pathlib.Path(__file__).resolve().parents[1]
for k,p in {"YOLO_CONFIG_DIR":"cache/ultralytics","MPLCONFIGDIR":"cache/matplotlib","TORCH_HOME":"cache/torch","XDG_CACHE_HOME":"cache","TMP":"cache/tmp","TEMP":"cache/tmp"}.items():
    os.environ[k]=str(R/p);(R/p).mkdir(exist_ok=True,parents=True)
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
os.environ["OMP_NUM_THREADS"]="2"
from ultralytics import YOLO
import torch
torch.set_num_threads(2)
yaml=str(R/"eval"/"both_unseen"/"data.yaml")
models={"YOLO26n":R.parent/"fly_rm320"/"models"/"best.pt","YOLOv8n":R/"models"/"best.pt"}
rows=[]
for name,p in models.items():
    model=YOLO(str(p))
    result=model.val(data=yaml,imgsz=320,batch=1,workers=0,device="cpu",project=str(R/"reports"),name=f"both_unseen_{name}",plots=False,exist_ok=True,verbose=False)
    row={"model":name,"samples":3,"precision":float(result.box.mp),"recall":float(result.box.mr),"map50":float(result.box.map50),"map50_95":float(result.box.map)}
    rows.append(row);print("UNSEEN",json.dumps(row),flush=True)
(R/"reports"/"comparison_unseen3.json").write_text(json.dumps(rows,indent=2),encoding="utf8")
