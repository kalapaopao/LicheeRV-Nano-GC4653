// Isolated GC4653 native-RAW only diagnostic.
// No JPEG, VENC, HTTP, GUI, image repair, ISP setting mutations, or in-loop writes.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <csignal>
#include <ctime>
#include <fcntl.h>
#include <unistd.h>
extern "C" {
#include "sample_comm.h"
}
static volatile sig_atomic_t running=1;
static void on_signal(int){running=0;}
static double now_s(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void copy_proc(const char* path,const char* dst){
    int in=open(path,O_RDONLY);if(in<0)return;
    int out=open(dst,O_CREAT|O_EXCL|O_WRONLY,0644);if(out<0){close(in);return;}
    char chunk[512];ssize_t n;
    while((n=read(in,chunk,sizeof(chunk)))>0) {
        const char *p=chunk;ssize_t left=n;
        while(left>0){ssize_t m=write(out,p,left);if(m<=0)break;p+=m;left-=m;}
    }
    close(out);close(in);
}
static void status(const char* dir,const char* phase){
    const char* names[]={"vi","vi_dbg","mipi"};
    const char* paths[]={"/proc/cvitek/vi","/proc/cvitek/vi_dbg","/proc/mipi-rx"};
    for(int i=0;i<3;i++){
        char dst[512];snprintf(dst,sizeof(dst),"%s/%s-%s.txt",dir,phase,names[i]);
        copy_proc(paths[i],dst);
    }
}
static int save_raw(const char* dir){
    VI_DUMP_ATTR_S original{},requested{};
    int rc=CVI_VI_GetPipeDumpAttr(0,&original);
    if(rc){printf("MINRAW dump get_attr failed=%x\n",rc);return rc;}
    requested=original;requested.bEnable=CVI_TRUE;
    requested.u32Depth=1;requested.enDumpType=VI_DUMP_TYPE_RAW;
    rc=CVI_VI_SetPipeDumpAttr(0,&requested);
    if(rc){printf("MINRAW dump enable failed=%x\n",rc);return rc;}
    int good=0;
    for(int j=0;j<3 && running;j++){
        VIDEO_FRAME_INFO_S buffers[2]{};
        rc=CVI_VI_GetPipeFrame(0,buffers,1500);
        if(rc){printf("MINRAW raw_get_%d failed=%x\n",j,rc);continue;}
        const auto &v=buffers[0].stVFrame;
        printf("MINRAW raw_%d width=%u height=%u len=%u stride=%u pixel=%d compress=%d bayer=%d pts=%llu\n",
              j,v.u32Width,v.u32Height,v.u32Length[0],v.u32Stride[0],
              v.enPixelFormat,v.enCompressMode,v.enBayerFormat,(unsigned long long)v.u64PTS);
        if(v.u32Width==1280&&v.u32Height==720&&v.u32Length[0]==1280*720*3/2&&
           v.enCompressMode==COMPRESS_MODE_NONE){
            void *p=CVI_SYS_MmapCache(v.u64PhyAddr[0],v.u32Length[0]);
            if(p){
                CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0],p,v.u32Length[0]);
                char filename[512];snprintf(filename,sizeof(filename),"%s/bayer-%d.bin",dir,j);
                FILE *f=fopen(filename,"wb");
                if(f){if(fwrite(p,1,v.u32Length[0],f)==v.u32Length[0])good++;fclose(f);}
                CVI_SYS_Munmap(p,v.u32Length[0]);
            }
        }
        CVI_VI_ReleasePipeFrame(0,buffers);
        usleep(120000);
    }
    int restore=CVI_VI_SetPipeDumpAttr(0,&original);
    printf("MINRAW raw_saved=%d restore_dump_rc=%x\n",good,restore);
    return good>0 && !restore?0:1;
}
int main(int argc,char** argv){
    if(argc!=4){fprintf(stderr,"usage: minraw_spec 27 seconds output_dir\n");return 2;}
    if(strcmp(argv[1],"27"))return 2;
    const int sec=atoi(argv[2]);
    if(sec<8||sec>40)return 2;
    const char* dir=argv[3];
    setenv("MAIX_SENSOR_FPS","60",1);
    setenv("GC4653_MINRAW_MCLK",argv[1],1);
    setvbuf(stdout,nullptr,_IOLBF,0);
    signal(SIGINT,on_signal);signal(SIGTERM,on_signal);
    printf("MINRAW_SPEC begin MCLK=27 MHz HTS=%s 720P RAW-only\n",
           getenv("MINRAW_SPEC_HTS") ? getenv("MINRAW_SPEC_HTS") : "1600");
    SAMPLE_INI_CFG_S ini{};SAMPLE_VI_CONFIG_S cfg{};
    if(SAMPLE_COMM_VI_ParseIni(&ini)||ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT)return 3;
    ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;
    CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&cfg))return 4;
    // Match the earlier successful RAW diagnostic: disable VI channel tiling
    // before the pipeline starts. Otherwise GetPipeFrame can be compressed.
    cfg.astViInfo[0].stChnInfo.enCompressMode=COMPRESS_MODE_NONE;
    SIZE_S sz{1280,720};
    if(SAMPLE_PLAT_SYS_INIT(sz))return 5;
    if(SAMPLE_PLAT_VI_INIT(&cfg)){SAMPLE_COMM_SYS_Exit();return 6;}
    int rc=0;
    VI_CHN_ATTR_S channel{};
    rc=CVI_VI_GetChnAttr(0,0,&channel);
    if(!rc){channel.u32Depth=2;rc=CVI_VI_SetChnAttr(0,0,&channel);}
    if(!rc){
        VIDEO_FRAME_INFO_S f{};
        double warm=now_s();
        while(running&&now_s()-warm<4){
            if(!CVI_VI_GetChnFrame(0,0,&f,1000))
                CVI_VI_ReleaseChnFrame(0,0,&f);
        }
        status(dir,"before");
        double first=0,last=0;
        uint64_t firstpts=0,lastpts=0,prevpts=0;
        uint64_t count=0,dups=0,timeouts=0;
        double start=now_s();
        while(running&&now_s()-start<sec){
            if(CVI_VI_GetChnFrame(0,0,&f,1000)){timeouts++;continue;}
            double t=now_s();uint64_t pts=f.stVFrame.u64PTS;
            if(!count){first=t;firstpts=pts;}
            else if(pts<=prevpts)dups++;
            last=t;lastpts=pts;prevpts=pts;count++;
            CVI_VI_ReleaseChnFrame(0,0,&f);
        }
        double fps=count>1?(count-1)/(last-first):0;
        double ptsfps=count>1&&lastpts>firstpts?1.0e6*(count-1)/(lastpts-firstpts):0;
        printf("MINRAW count=%llu fps=%.4f pts_fps=%.4f duplicate=%llu timeouts=%llu\n",
             (unsigned long long)count,fps,ptsfps,(unsigned long long)dups,
             (unsigned long long)timeouts);
        status(dir,"after");
        int dump_rc=save_raw(dir);
        printf("MINRAW dump_rc=%d\n",dump_rc);
        char path[512];snprintf(path,sizeof(path),"%s/result.json",dir);
        FILE *out=fopen(path,"wb");
        if(out){fprintf(out,"{\"clock\":\"%s\",\"frames\":%llu,\"fps\":%.4f,\"pts_fps\":%.4f,\"duplicate_pts\":%llu,\"timeouts\":%llu,\"dump_rc\":%d}\n",argv[1],(unsigned long long)count,fps,ptsfps,(unsigned long long)dups,(unsigned long long)timeouts,dump_rc);fclose(out);}
        if(!count||timeouts||dump_rc)rc=8;
    }
    SAMPLE_COMM_VI_DestroyIsp(&cfg);
    SAMPLE_COMM_VI_DestroyVi(&cfg);
    SAMPLE_COMM_SYS_Exit();
    printf("MINRAW normal_cleanup rc=%d\n",rc);
    return rc;
}
