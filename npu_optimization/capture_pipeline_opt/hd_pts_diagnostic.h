#pragma once
// Experimental true-frame-matched 1280x720 NV21 image snapshots.
// The source VI frame is copied before it is released to the original VENC0.
#include <vector>
#include <atomic>
#include <cstring>
#include <algorithm>
#include "cvi_sys.h"
#include "cvi_vpss.h"
#include "yolo26_postprocess.h"

static inline bool capture_hd_nv21(const VIDEO_FRAME_INFO_S& frame, std::vector<uint8_t>& packed) {
    const VIDEO_FRAME_S& v=frame.stVFrame;
    if(v.u32Width!=1280 || v.u32Height!=720 || v.enPixelFormat!=PIXEL_FORMAT_NV21 ||
       !v.u64PhyAddr[0] || !v.u64PhyAddr[1] ||
       v.u32Stride[0]<1280 || v.u32Stride[1]<1280 ||
       v.u32Length[0]<(size_t)v.u32Stride[0]*720 ||
       v.u32Length[1]<(size_t)v.u32Stride[1]*360) return false;
    auto *y=(const uint8_t*)CVI_SYS_MmapCache(v.u64PhyAddr[0],v.u32Length[0]);
    auto *uv=(const uint8_t*)CVI_SYS_MmapCache(v.u64PhyAddr[1],v.u32Length[1]);
    if(!y || !uv) {
        if(y)CVI_SYS_Munmap((void*)y,v.u32Length[0]);
        if(uv)CVI_SYS_Munmap((void*)uv,v.u32Length[1]);
        return false;
    }
    const bool valid=
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0],(void*)y,v.u32Length[0])==0 &&
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[1],(void*)uv,v.u32Length[1])==0;
    if(valid) {
        packed.resize(1280u*720u*3u/2u);
        for(unsigned row=0;row<720;row++)
            std::memcpy(packed.data()+row*1280,y+row*v.u32Stride[0],1280);
        for(unsigned row=0;row<360;row++)
            std::memcpy(packed.data()+921600+row*1280,uv+row*v.u32Stride[1],1280);
    }
    CVI_SYS_Munmap((void*)uv,v.u32Length[1]);
    CVI_SYS_Munmap((void*)y,v.u32Length[0]);
    return valid;
}

static inline void hd_nv21_boxes(std::vector<uint8_t>& packed, const std::vector<YoloBox>& boxes){
    if(packed.size()!=1280u*720u*3u/2u)return;
    uint8_t *y=packed.data();
    uint8_t *vu=y+921600;
    const auto put=[&](int x,int row) {
        if(x<0 || x>=1280 || row<0 || row>=720)return;
        y[row*1280+x]=149;
        const size_t idx=(row/2)*1280+(x&~1);
        vu[idx]=21;vu[idx+1]=43;
    };
    for(const auto &b:boxes){
        const int x1=std::max(0,static_cast<int>(b.x1));
        const int y1=std::max(0,static_cast<int>(b.y1));
        const int x2=std::min(1279,static_cast<int>(b.x2));
        const int y2=std::min(719,static_cast<int>(b.y2));
        if(x2<=x1 || y2<=y1)continue;
        for(int t=0;t<4;t++){
            for(int x=x1;x<=x2;x++){put(x,y1+t);put(x,y2-t);}
            for(int row=y1;row<=y2;row++){put(x1+t,row);put(x2-t,row);}
        }
    }
}
