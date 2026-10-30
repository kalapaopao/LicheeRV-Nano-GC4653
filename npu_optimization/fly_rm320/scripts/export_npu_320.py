"""Export isolated YOLO26 checkpoint to raw one-to-many ONNX in D: project only."""
import os, pathlib
root=pathlib.Path(__file__).resolve().parents[1]
for k,v in {"YOLO_CONFIG_DIR":str(root/"cache"/"ultralytics"),"MPLCONFIGDIR":str(root/"cache"/"matplotlib"),"TORCH_HOME":str(root/"cache"/"torch"),"XDG_CACHE_HOME":str(root/"cache")}.items():
    os.environ[k]=v
    pathlib.Path(v).mkdir(parents=True,exist_ok=True)
from ultralytics import YOLO
import onnx
weight=root/"models"/"best.pt"
print("SOURCE",weight,flush=True)
model=YOLO(str(weight))
# YOLO26 default end-to-end output is [1,300,6]. Disable it to get [1,5,2100] raw head for CV181x.
model.model.model[-1].end2end = False
result=model.export(format="onnx",imgsz=320,opset=13,half=False,dynamic=False,simplify=False,nms=False,device="cpu")
onnx_path=pathlib.Path(str(result))
print("ONNX_PATH",onnx_path,flush=True)
m=onnx.load(str(onnx_path))
outs=[]
for value in m.graph.output:
    dims=[d.dim_value if d.HasField("dim_value") else d.dim_param for d in value.type.tensor_type.shape.dim]
    outs.append((value.name,dims))
print("ONNX_OUTPUTS",outs,flush=True)
assert len(outs)==1 and len(outs[0][1])>=3 and (2100 in outs[0][1]), "EXPECTED_RAW_2100, DO NOT DEPLOY NMS output"
print("RAW_EXPORT_CONFIRMED",flush=True)
