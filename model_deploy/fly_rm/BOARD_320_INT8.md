# fly_rm 320×320 INT8 板端部署

## 文件

模型：`/code/camera/models/fly_rm/fly_rm_320_int8.cvimodel`

输入：`images`，形状 `1×3×320×320`，`fp32`，BGR，像素范围 `0~255`。

输出：`output0_Concat_f32`，形状 `1×5×2100×1`。这是 YOLO26 原始检测头输出，仍需在应用层完成候选框解码和 NMS。

## 板端测速

```sh
export LD_LIBRARY_PATH=/usr/bin/lib
/usr/bin/model_runner \
  --model /code/camera/models/fly_rm/fly_rm_320_int8.cvimodel \
  --input /code/camera/models/fly_rm/sample_input_320.npz \
  --output /code/camera/models/fly_rm/output_320_int8.npz \
  --enable-timer \
  --count 100
```

当前实测：100 次耗时 3507.19 ms，平均 35.071 ms，约 28.51 FPS。

## 真实摄像头接入

`record80` 已增加可选的 `CVI_NN` 推理路径。启动时设置模型路径：

```sh
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd:/usr/bin/lib
export FLY_RM_MODEL=/code/camera/models/fly_rm/fly_rm_320_int8.cvimodel
sh /code/camera/modules/record80/run_board_yolo320.sh
```

日志会输出 `capture_frames`、`infer`、`infer_errors` 和 `infer_avg_ms`。一次真实 GC4653 测试得到：采集约 16.6 FPS，推理完成 61 帧，跳过 245 帧，平均推理约 48.9 ms。模型输入和运行时调用已验证，当前瓶颈是摄像头帧转换和推理调用仍在采集路径上。

## 代码边界

`modules/record80` 继续保持原来的 80FPS 采集程序。板端模型放在独立目录，不覆盖录像程序和系统模型。

把模型接入真实摄像头帧还需要三段固定逻辑：NV21 转 BGR、缩放到 320×320、YOLO26 解码/NMS。当前仓库没有把 `CVI_NN` 头文件和链接库纳入 `record80` 的构建输入，因此暂不把未验证的 SDK 声明复制进主程序。

## 回退

删除本次模型目录即可恢复原板端状态：

```sh
rm -rf /code/camera/models/fly_rm
```
