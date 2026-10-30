"""Compare new board SG2002 output and Windows ONNX on SAME VPSS NV21 frame."""
import os, pathlib, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
os.environ["OMP_NUM_THREADS"]="2"
os.environ["MKL_NUM_THREADS"]="2"
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
import numpy as np, cv2, onnxruntime as ort
sessdir=ROOT/"reports"/"session_20840_1199"
raw=np.fromfile(sessdir/"vpss_first_320.nv21",dtype=np.uint8)
assert raw.size==320*320*3//2,(raw.shape,raw.size)
nv21=raw.reshape((480,320))
board=np.fromfile(sessdir/"npu_first_output.bin",dtype=np.float32)
assert board.size==5*2100,(board.shape,board.size)
board=board.reshape((1,5,2100))
session=ort.InferenceSession(str(ROOT/"models"/"best.onnx"),providers=["CPUExecutionProvider"])
name=session.get_inputs()[0].name
reports=[]
for c,mode in [("RGB",cv2.COLOR_YUV2RGB_NV21),("BGR",cv2.COLOR_YUV2BGR_NV21)]:
 rgb=cv2.cvtColor(nv21,mode)
 x=rgb.astype(np.float32).transpose(2,0,1)[None]/255.
 ref=session.run(None,{name:x})[0]
 assert ref.shape==board.shape,(ref.shape,board.shape)
 err=np.abs(ref-board)
 e=ref.reshape(-1)
 b=board.reshape(-1)
 cos=float(np.dot(e,b)/(np.linalg.norm(e)*np.linalg.norm(b)+1e-12))
 conferr=err[0,4,:]
 confidence_ref=ref[0,4,:]
 confidence_board=board[0,4,:]
 out=dict(mode=c,onnx_shape=list(ref.shape),finite_board_ratio=float(np.isfinite(board).mean()),cosine_all=cos,mae=float(err.mean()),rmse=float(np.sqrt((err**2).mean())),mae_box=float(err[0,:4].mean()),mae_conf=float(conferr.mean()),max_abs_diff=float(err.max()),
 max_conf_onnx=float(confidence_ref.max()),max_conf_board=float(confidence_board.max()),confidence_cosine=float(np.dot(confidence_ref,confidence_board)/(np.linalg.norm(confidence_ref)*np.linalg.norm(confidence_board)+1e-12)),
 above05_onnx=int((confidence_ref>0.5).sum()),above05_board=int((confidence_board>0.5).sum()),
 within_0p1=float((err<0.1).mean()))
 reports.append(out)
 print("COMPARE",json.dumps(out,ensure_ascii=False),flush=True)
(ROOT/"reports"/"board_onnx_alignment.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding="utf-8")
