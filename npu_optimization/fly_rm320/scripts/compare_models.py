"""Read original train datasets; copy validation images ONLY into D: before YOLO val.
No write to user training directories. Compare models using same data per evaluation.
"""
from pathlib import Path
import os, shutil, json, hashlib, time
R=Path(__file__).resolve().parents[1]
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
os.environ["OMP_NUM_THREADS"]="2"
os.environ["MKL_NUM_THREADS"]="2"
for key,sub in {"YOLO_CONFIG_DIR":"cache/ultralytics","MPLCONFIGDIR":"cache/matplotlib","TORCH_HOME":"cache/torch","XDG_CACHE_HOME":"cache","TMP":"cache/tmp","TEMP":"cache/tmp"}.items():
    os.environ[key]=str(R/sub); (R/sub).mkdir(parents=True,exist_ok=True)
old_data=Path(r"E:\study\X-AnyLabeling-main\xanylabeling_data\trainer\ultralytics\datasets\detect\fly_rm_20261028_154724")
new_data=Path(r"C:\Users\admin\xanylabeling_data\trainer\ultralytics\datasets\detect\fly_rm_20261030_213613")
weights={
 "old640":Path(r"E:\study\X-AnyLabeling-main\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm\weights\best.pt"),
 "new320":R/"models"/"best.pt"
}
sources={"old":old_data,"new":new_data}
def files(src,typ,part):
    return {x.stem:x for x in (src/typ/part).iterdir() if x.is_file() and x.suffix.lower() in ((".jpg",".jpeg",".png",".bmp") if typ=="images" else (".txt",))}
def digest(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(2**20),b""):h.update(b)
    return h.hexdigest()
meta={}
for name,data in sources.items():
    tr=files(data,"images","train")
    va=files(data,"images","val")
    labels=files(data,"labels","val")
    assert len(va)==31 and len(labels)==31, (name,len(va),len(labels))
    target=R/"eval"/name
    for typ in ["images","labels"]:(target/typ/"val").mkdir(parents=True,exist_ok=True)
    for f in va.values():shutil.copy2(f,target/"images"/"val"/f.name)
    for f in labels.values():shutil.copy2(f,target/"labels"/"val"/f.name)
    yaml=target/"data.yaml"
    yaml.write_text("path: "+str(target).replace("\\","/")+"\ntrain: images/val\nval: images/val\nnames:\n  0: target\nnc: 1\n",encoding="utf-8")
    meta[name]={"train_count":len(tr),"val_count":len(va),"val_label_count":len(labels),
                "train_ids":set(tr),"val_ids":set(va),"label_ids":set(labels),
                "yaml":str(yaml),"sample_hashes":{k:digest(v) for k,v in list(va.items())[:3]}}
meta_s={k:{a:(sorted(b) if isinstance(b,set) else b) for a,b in v.items()} for k,v in meta.items()}
meta_s["overlap"]={
 "val_both":len(meta["old"]["val_ids"] & meta["new"]["val_ids"]),
 "old_val_in_new_train":len(meta["old"]["val_ids"] & meta["new"]["train_ids"]),
 "new_val_in_old_train":len(meta["new"]["val_ids"] & meta["old"]["train_ids"])
}
(R/"reports"/"split_analysis.json").write_text(json.dumps(meta_s,indent=2,ensure_ascii=False),encoding="utf-8")
print("SPLIT",meta_s["overlap"],flush=True)
from ultralytics import YOLO
import torch
device="cpu"
torch.set_num_threads(2)
results=[]
for dataset in ["old","new"]:
 for modelname,weight in weights.items():
  for size in [320]:
   print("START",dataset,modelname,size,flush=True)
   t=time.monotonic()
   model=YOLO(str(weight))
   m=model.val(data=meta[dataset]["yaml"],imgsz=size,batch=1,device=device,workers=0,project=str(R/"reports"),name="val_"+dataset+"_"+modelname+"_"+str(size),exist_ok=True,plots=False,save_json=False,verbose=False,rect=False)
   row={"dataset":dataset,"model":modelname,"size":size,"precision":float(m.box.mp),"recall":float(m.box.mr),"map50":float(m.box.map50),"map50_95":float(m.box.map),"elapsed":round(time.monotonic()-t,2),"speed_ms":dict(m.speed)}
   results.append(row)
   print("RESULT",json.dumps(row,ensure_ascii=False),flush=True)
   (R/"reports"/"comparison.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
