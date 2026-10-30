#pragma once
// Experimental: VENC1 needs a VENC-readable VB, not an unowned VPSS output.
// Copy the 320x320 NV21 image to a dedicated VB pool before overlay+encoding.
#include <cstdint>
#include <cstring>
#include <cstdio>
#include "cvi_vb.h"
#include "cvi_sys.h"
#include <linux/cvi_comm_video.h>

class BakedVbPool {
    VB_POOL pool_=VB_INVALID_POOLID;
    static constexpr CVI_U32 blk_size_=200704; // 196 KiB aligned
public:
    bool init() {
        VB_POOL_CONFIG_S cfg{};
        cfg.u32BlkSize=blk_size_;
        cfg.u32BlkCnt=3;
        cfg.enRemapMode=VB_REMAP_MODE_NOCACHE;
        std::snprintf(cfg.acName,sizeof(cfg.acName),"yolo_baked_preview");
        pool_=CVI_VB_CreatePool(&cfg);
        std::printf("BAKED_VB_POOL id=%u block_bytes=%u\n",pool_,blk_size_);
        return pool_!=VB_INVALID_POOLID;
    }
    void close(){
        if(pool_!=VB_INVALID_POOLID){
            const int rc=CVI_VB_DestroyPool(pool_);
            std::printf("BAKED_VB_POOL_CLOSE rc=0x%x\n",rc);
            pool_=VB_INVALID_POOLID;
        }
    }
    bool copy(const VIDEO_FRAME_INFO_S& source, VIDEO_FRAME_INFO_S &out, VB_BLK &block) {
        block=VB_INVALID_HANDLE;
        if(pool_==VB_INVALID_POOLID) return false;
        const auto& s=source.stVFrame;
        if(s.u32Width!=320 || s.u32Height!=320 || s.enPixelFormat!=PIXEL_FORMAT_NV21 ||
           s.u32Stride[0]<320 || s.u32Stride[1]<320) return false;
        const size_t ybytes=(size_t)s.u32Stride[0]*320;
        const size_t cbytes=(size_t)s.u32Stride[1]*160;
        const size_t coff=(ybytes+63u)&~63u;
        if(ybytes>s.u32Length[0] || cbytes>s.u32Length[1] ||
           coff+cbytes>blk_size_) return false;
        block=CVI_VB_GetBlock(pool_,blk_size_);
        if(block==VB_INVALID_HANDLE) return false;
        CVI_U64 phy=CVI_VB_Handle2PhysAddr(block);
        auto *dst=static_cast<uint8_t*>(CVI_SYS_Mmap(phy,blk_size_));
        auto *srcy=static_cast<uint8_t*>(CVI_SYS_MmapCache(s.u64PhyAddr[0],s.u32Length[0]));
        auto *srcc=static_cast<uint8_t*>(CVI_SYS_MmapCache(s.u64PhyAddr[1],s.u32Length[1]));
        bool ok=dst && srcy && srcc;
        if(ok) ok=CVI_SYS_IonInvalidateCache(s.u64PhyAddr[0],srcy,s.u32Length[0])==0 &&
                  CVI_SYS_IonInvalidateCache(s.u64PhyAddr[1],srcc,s.u32Length[1])==0;
        if(ok){
            std::memcpy(dst,srcy,ybytes);
            std::memcpy(dst+coff,srcc,cbytes);
            out=source;
            out.u32PoolId=pool_;
            out.stVFrame.u64PhyAddr[0]=phy;
            out.stVFrame.u64PhyAddr[1]=phy+coff;
            out.stVFrame.u64PhyAddr[2]=0;
            out.stVFrame.pu8VirAddr[0]=out.stVFrame.pu8VirAddr[1]=out.stVFrame.pu8VirAddr[2]=nullptr;
            out.stVFrame.pPrivateData=nullptr;
            out.stVFrame.u32Length[0]=(CVI_U32)ybytes;
            out.stVFrame.u32Length[1]=(CVI_U32)cbytes;
            out.stVFrame.u32Length[2]=0;
        }
        if(srcc)CVI_SYS_Munmap(srcc,s.u32Length[1]);
        if(srcy)CVI_SYS_Munmap(srcy,s.u32Length[0]);
        if(dst)CVI_SYS_Munmap(dst,blk_size_);
        if(!ok){CVI_VB_ReleaseBlock(block);block=VB_INVALID_HANDLE;}
        return ok;
    }
    void release(VB_BLK b){if(b!=VB_INVALID_HANDLE)CVI_VB_ReleaseBlock(b);}
};
