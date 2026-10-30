#pragma once
// Draw a green detection border directly into the SAME 320x320 NV21 frame
// that was just used for NPU inference. Never touch the 1280x720 recording
// frame or the VI buffers. Uses the VPSS frame while ownership is held.
#include <algorithm>
#include <cstdint>
#include <vector>
#include "cvi_sys.h"
#include "cvi_vpss.h"
#include "yolo26_postprocess.h"

static bool baked_nv21_boxes(VIDEO_FRAME_INFO_S &frame,
                             const std::vector<YoloBox> &boxes) {
    const auto &v = frame.stVFrame;
    if (v.u32Width != 320 || v.u32Height != 320 ||
        v.enPixelFormat != PIXEL_FORMAT_NV21 || !v.u64PhyAddr[0] ||
        !v.u64PhyAddr[1] || v.u32Stride[0] < 320 ||
        v.u32Stride[1] < 320) return false;
    const size_t ylen = static_cast<size_t>(v.u32Stride[0]) * 320;
    const size_t clen = static_cast<size_t>(v.u32Stride[1]) * 160;
    if (v.u32Length[0] < ylen || v.u32Length[1] < clen) return false;
    auto *y = static_cast<uint8_t*>(CVI_SYS_MmapCache(v.u64PhyAddr[0], v.u32Length[0]));
    if (!y) return false;
    auto *vu = static_cast<uint8_t*>(CVI_SYS_MmapCache(v.u64PhyAddr[1], v.u32Length[1]));
    if (!vu) { CVI_SYS_Munmap(y,v.u32Length[0]); return false; }
    // CPU writes change the physical frame for the secondary hardware JPEG.
    const bool invalidate =
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0], y, v.u32Length[0]) == 0 &&
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[1], vu, v.u32Length[1]) == 0;
    bool success = invalidate;
    if (success) {
        auto put = [&](int x, int yy) {
            if(x<0 || x>=320 || yy<0 || yy>=320)return;
            y[yy*v.u32Stride[0]+x] = 149; // bright green Y
            size_t c = (yy/2)*v.u32Stride[1] + (x&~1);
            vu[c] = 21; vu[c+1] = 43;      // NV21: V,U
        };
        for (const auto &b: boxes) {
            const int x1=std::max(0,static_cast<int>(b.x1/4));
            const int x2=std::min(319,static_cast<int>(b.x2/4));
            const int y1=std::max(0,static_cast<int>(b.y1/4 + 70));
            const int y2=std::min(319,static_cast<int>(b.y2/4 + 70));
            if (x2<=x1 || y2<=y1) continue;
            for (int t=0;t<3;t++) {
                for (int x=x1;x<=x2;x++){put(x,y1+t);put(x,y2-t);}
                for (int yy=y1;yy<=y2;yy++){put(x1+t,yy);put(x2-t,yy);}
            }
        }
        const bool y_ok = CVI_SYS_IonFlushCache(v.u64PhyAddr[0],y,v.u32Length[0])==0;
        const bool uv_ok = CVI_SYS_IonFlushCache(v.u64PhyAddr[1],vu,v.u32Length[1])==0;
        success = y_ok && uv_ok;
    }
    CVI_SYS_Munmap(y,v.u32Length[0]);
    CVI_SYS_Munmap(vu,v.u32Length[1]);
    return success;
}
