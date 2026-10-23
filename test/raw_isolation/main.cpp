// Native GC4653 frame benchmark. Uses CVI VI buffers, no JPEG/disk work in timed loop.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <csignal>
#include <cstdint>
#include <ctime>
#include <initializer_list>
#include <unistd.h>
extern "C" {
#include "sample_comm.h"
#include "cvi_ae.h"
int gc4653_read_register(VI_PIPE,int);
}
static volatile sig_atomic_t running=1;
static void stop(int){ running=0; }
static double seconds(){ timespec t{}; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec/1e9; }
static void dump_status(const char* dir,const char* phase){
    for(const char* name:{"vi","vi_dbg"}) {
        char path[512]; snprintf(path,sizeof(path),"%s/%s-%s.txt",dir,phase,name);
        char proc[64]; snprintf(proc,sizeof(proc),"/proc/cvitek/%s",name);
        FILE *in=fopen(proc,"rb"),*out=fopen(path,"wb"); char buf[4096]; size_t n;
        if(in&&out) while((n=fread(buf,1,sizeof(buf),in))) fwrite(buf,1,n,out);
        if(in) fclose(in); if(out) fclose(out);
    }
}
static bool snapshot(const VIDEO_FRAME_INFO_S& frame,const char* dir){
    char path[512]; snprintf(path,sizeof(path),"%s/frame.nv21",dir);
    FILE* fp=fopen(path,"wb"); if(!fp) return false;
    auto& v=frame.stVFrame;
    for(int p=0;p<2;p++){
        int rows=p?v.u32Height/2:v.u32Height;
        size_t size=v.u32Stride[p]*rows;
        void* addr=CVI_SYS_Mmap(v.u64PhyAddr[p],size);
        if(!addr){fclose(fp);return false;}
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[p],addr,size);
        for(int y=0;y<rows;y++) fwrite((char*)addr+y*v.u32Stride[p],1,v.u32Width,fp);
        CVI_SYS_Munmap(addr,size);
    }
    fclose(fp); return true;
}
/* RAW probe: capture three pre-ISP Bayer frames, no JPEG/HTTP/GUI.
 * ISP/VI initialization remains required to drive the sensor and CSI.
 */
static void capture_bayer(const char* dir) {
    VI_DUMP_ATTR_S old{}, d{};
    int rc=CVI_VI_GetPipeDumpAttr(0,&old);
    printf("RAW GetPipeDumpAttr rc=%x\n",rc);
    if(rc) return;
    d.bEnable=CVI_TRUE; d.u32Depth=1; d.enDumpType=VI_DUMP_TYPE_RAW;
    rc=CVI_VI_SetPipeDumpAttr(0,&d);
    printf("RAW SetPipeDumpAttr rc=%x\n",rc);
    if(rc) return;
    for(int k=0;k<3 && running;k++){
        VIDEO_FRAME_INFO_S f[2]{};
        rc=CVI_VI_GetPipeFrame(0,f,1500);
        printf("RAW GetPipeFrame k=%d rc=%x\n",k,rc);
        if(rc) continue;
        auto &v=f[0].stVFrame;
        printf("RAW geometry k=%d w=%u h=%u len=%u fmt=%d Bayer=%d compress=%d pts=%llu\n",
               k,v.u32Width,v.u32Height,v.u32Length[0],v.enPixelFormat,v.enBayerFormat,
               v.enCompressMode,(unsigned long long)v.u64PTS);
        if(v.u32Width==1280 && v.u32Height==720 && v.u32Length[0]==1382400
            && v.enCompressMode==COMPRESS_MODE_NONE){
            void* mem=CVI_SYS_MmapCache(v.u64PhyAddr[0],v.u32Length[0]);
            if(mem){
                CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0],mem,v.u32Length[0]);
                char path[512];snprintf(path,sizeof(path),"%s/raw-%d.bin",dir,k);
                FILE *fp=fopen(path,"wb");
                if(fp){size_t n=fwrite(mem,1,v.u32Length[0],fp);
                    printf("RAW saved=%s bytes=%zu\n",path,n);fclose(fp);}
                CVI_SYS_Munmap(mem,v.u32Length[0]);
            }
        }else{
            printf("RAW rejected unexpected geometry/layout; no blind decode\n");
        }
        CVI_VI_ReleasePipeFrame(0,f);
        usleep(180000);
    }
    printf("RAW restore SetPipeDumpAttr rc=%x\n",CVI_VI_SetPipeDumpAttr(0,&old));
}

int main(int argc,char** argv){
    if(argc!=4&&argc!=5){fprintf(stderr,"Usage: %s FPS SECONDS REPORT_DIR\n",argv[0]);return 2;}
    int fps=atoi(argv[1]); double duration=atof(argv[2]); const char* dir=argv[3];
    if((fps!=30&&fps!=60&&fps!=80)||duration<3||duration>300) return 2;
    char fpsstr[16]; snprintf(fpsstr,sizeof(fpsstr),"%d",fps); setenv("MAIX_SENSOR_FPS",fpsstr,1);
    SAMPLE_INI_CFG_S ini{}; SAMPLE_VI_CONFIG_S config{};
    int rc=SAMPLE_COMM_VI_ParseIni(&ini);
    if(rc!=0){fprintf(stderr,"ParseIni failed %x\n",rc);return 3;}
    if(ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT){fprintf(stderr,"Expected GC4653 config\n");return 3;}
    if(fps>30) ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;
    CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&config)!=0) return 3;
    /* Required for RAW12 interpretation; keep this identical in all cases. */
    config.astViInfo[0].stChnInfo.enCompressMode=COMPRESS_MODE_NONE;
    printf("RAW_ISOLATION channel_config_compress=%d\n",config.astViInfo[0].stChnInfo.enCompressMode);
    SIZE_S size{(CVI_U32)(fps>30?1280:2560),(CVI_U32)(fps>30?720:1440)};
    if(SAMPLE_PLAT_SYS_INIT(size)!=0) return 4;
    if(SAMPLE_PLAT_VI_INIT(&config)!=0) return 5;
    signal(SIGINT,stop); signal(SIGTERM,stop);
    VI_CHN_ATTR_S attr{};
    CVI_VI_GetChnAttr(0,0,&attr); attr.u32Depth=2;
    if(CVI_VI_SetChnAttr(0,0,&attr)!=0) {running=0; rc=6;}
    if(argc==5 && strcmp(argv[4],"manual")==0) {
        ISP_EXPOSURE_ATTR_S e{}; CVI_ISP_GetExposureAttr(0,&e);
        e.enOpType=OP_TYPE_MANUAL; e.stManual.enGainType=AE_TYPE_GAIN;
        e.stManual.enExpTimeOpType=e.stManual.enAGainOpType=e.stManual.enDGainOpType=e.stManual.enISPDGainOpType=OP_TYPE_MANUAL;
        e.stManual.u32ExpTime=5000; e.stManual.u32AGain=4096; e.stManual.u32DGain=1024; e.stManual.u32ISPDGain=1024;
        printf("manual exposure rc=%x\n",CVI_ISP_SetExposureAttr(0,&e));
    }

    // Allow sensor/AE/AWB to settle while draining frames.
    double warm=seconds(); VIDEO_FRAME_INFO_S frame{};
    while(running&&seconds()-warm<4){
        if(CVI_VI_GetChnFrame(0,0,&frame,1000)==0) CVI_VI_ReleaseChnFrame(0,0,&frame);
    }
    if(argc==5 && strcmp(argv[4],"refresh")==0) {
        ISP_PUB_ATTR_S pub{};
        CVI_ISP_GetPubAttr(0,&pub);
        printf("PUB before refresh fps=%f size=%ux%u\n",pub.f32FrameRate,pub.stSnsSize.u32Width,pub.stSnsSize.u32Height);
        pub.f32FrameRate=fps>30?60:30;
        printf("PUB refresh rc=%x\n",CVI_ISP_SetPubAttr(0,&pub));
        double settle=seconds();
        while(running&&seconds()-settle<3)
            if(CVI_VI_GetChnFrame(0,0,&frame,1000)==0) CVI_VI_ReleaseChnFrame(0,0,&frame);
    }

    capture_bayer(dir); // isolate pre-ISP source, no VENC/HTTP threads
    dump_status(dir,"before");
    char csvpath[512]; snprintf(csvpath,sizeof(csvpath),"%s/frames.csv",dir);
    FILE* csv=nullptr; // empty benchmark: no per-frame disk writes if(csv) fprintf(csv,"host_seconds,pts_us,time_ref\n");
    uint64_t count=0,dup=0,timeouts=0,prevpts=0,firstpts=0,lastpts=0,gaps=0;
    timespec cpu0{},cpu1{}; clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&cpu0);
    double t0=seconds(),first=0,last=0;
    while(running&&seconds()-t0<duration){
        int ret=CVI_VI_GetChnFrame(0,0,&frame,1000);
        if(ret!=0){if(!running) break; timeouts++;continue;}
        double now=seconds(); uint64_t pts=frame.stVFrame.u64PTS;
        if(pts&&pts<=prevpts) dup++;
        if(count==0){first=now; firstpts=pts;}
        else if(pts>prevpts+uint64_t(1.8e6/fps)) gaps++;
        last=now; lastpts=pts; prevpts=pts;
        if(csv) fprintf(csv,"%.9f,%llu,%u\n",now,(unsigned long long)pts,frame.stVFrame.u32TimeRef);
        count++; CVI_VI_ReleaseChnFrame(0,0,&frame);
    }
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&cpu1);
    printf("CPU percent=%.3f\n",100.0*((cpu1.tv_sec-cpu0.tv_sec)+(cpu1.tv_nsec-cpu0.tv_nsec)/1e9)/(seconds()-t0));
    if(csv) fclose(csv);
    ISP_EXP_INFO_S exp{};
    CVI_ISP_QueryExposureInfo(0,&exp);
    printf("AE exposure_us=%u again=%u dgain=%u isp_gain=%u luma=%u fps=%u\n",
        exp.u32ExpTime,exp.u32AGain,exp.u32DGain,exp.u32ISPDGain,exp.u8AveLum,exp.u32Fps);
    printf("REG VTS=%d exposure=%d\n",(gc4653_read_register(0,0x0340)<<8)|gc4653_read_register(0,0x0341),(gc4653_read_register(0,0x0202)<<8)|gc4653_read_register(0,0x0203));

    dump_status(dir,"after");
    if(CVI_VI_GetChnFrame(0,0,&frame,1000)==0){
        snapshot(frame,dir); CVI_VI_ReleaseChnFrame(0,0,&frame);
    }
    double elapsed=last-first;
    double actual=count>1?(count-1)/elapsed:0;
    double ptsfps=count>1&&lastpts>firstpts?(count-1)*1e6/(lastpts-firstpts):0;
    char path[512]; snprintf(path,sizeof(path),"%s/result.json",dir);
    FILE* out=fopen(path,"w");
    if(out){
        fprintf(out,"{\"requested_fps\":%d,\"width\":%u,\"height\":%u,\"frames\":%llu,\"host_fps\":%.4f,\"pts_fps\":%.4f,\"duplicate_pts\":%llu,\"timeouts\":%llu,\"large_intervals\":%llu}\n",
          fps,size.u32Width,size.u32Height,(unsigned long long)count,actual,ptsfps,
          (unsigned long long)dup,(unsigned long long)timeouts,(unsigned long long)gaps);
        fclose(out);
    }
    printf("RESULT requested=%d frames=%llu host_fps=%.3f pts_fps=%.3f duplicate_pts=%llu timeouts=%llu\n",
          fps,(unsigned long long)count,actual,ptsfps,(unsigned long long)dup,(unsigned long long)timeouts);
    SAMPLE_COMM_VI_DestroyIsp(&config);
    SAMPLE_COMM_VI_DestroyVi(&config);
    SAMPLE_COMM_SYS_Exit();
    return rc;
}
