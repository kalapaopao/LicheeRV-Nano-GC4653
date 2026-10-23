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
    // In this test tree, the selected 720P60 driver slot carries the isolated
    // 1920x1080 sensor window; allocate VI buffers to the actual advertised mode.
    SIZE_S size{(CVI_U32)(fps>30?1920:2560),(CVI_U32)(fps>30?1080:1440)};
    if(SAMPLE_PLAT_SYS_INIT(size)!=0) return 4;
    if(SAMPLE_PLAT_VI_INIT(&config)!=0) return 5;
    signal(SIGINT,stop); signal(SIGTERM,stop);
    VI_CHN_ATTR_S attr{};
    CVI_VI_GetChnAttr(0,0,&attr); attr.u32Depth=2;
    if(CVI_VI_SetChnAttr(0,0,&attr)!=0) {running=0; rc=6;}
    const char *test_mode=argc==5?argv[4]:"auto";
    if(strcmp(test_mode,"auto") && strcmp(test_mode,"factory") && strcmp(test_mode,"manual")) return 2;
    // Match the working factory test: let VI/ISP initialize, then set the ISP's
    // expected rate to 60fps before timed measurement. Otherwise default AE can
    // lengthen VTS to 2400 and make this appear to be a sensor FPS limit.
    double warm=seconds(); VIDEO_FRAME_INFO_S frame{}; bool configured=false;
    while(running&&seconds()-warm<7){
        if(CVI_VI_GetChnFrame(0,0,&frame,1000)==0){
            if(!configured && seconds()-warm>=2){
                ISP_PUB_ATTR_S pub{}; int e=CVI_ISP_GetPubAttr(0,&pub);
                if(!e){pub.f32FrameRate=fps>30?60:30;e=CVI_ISP_SetPubAttr(0,&pub);}
                printf("LAB_ISP_PUB_FPS=%d rc=%x\n",fps>30?60:30,e);
                if(!strcmp(test_mode,"factory")){
                    ISP_EXPOSURE_ATTR_S ae{};e=CVI_ISP_GetExposureAttr(0,&ae);
                    if(!e){ae.enOpType=OP_TYPE_AUTO;ae.stAuto.enAEMode=AE_MODE_FIX_FRAME_RATE;ae.stAuto.stExpTimeRange.u32Max=12000;e=CVI_ISP_SetExposureAttr(0,&ae);}
                    printf("LAB_FACTORY_AE_MAX_US=12000 rc=%x\n",e);
                }else if(!strcmp(test_mode,"manual")){
                    ISP_EXPOSURE_ATTR_S ae{};e=CVI_ISP_GetExposureAttr(0,&ae);
                    if(!e){ae.enOpType=OP_TYPE_MANUAL;ae.stManual.enGainType=AE_TYPE_GAIN;
                        ae.stManual.enExpTimeOpType=ae.stManual.enAGainOpType=ae.stManual.enDGainOpType=ae.stManual.enISPDGainOpType=OP_TYPE_MANUAL;
                        ae.stManual.u32ExpTime=5000;ae.stManual.u32AGain=4096;ae.stManual.u32DGain=1024;ae.stManual.u32ISPDGain=1024;
                        e=CVI_ISP_SetExposureAttr(0,&ae);}
                    printf("LAB_MANUAL_EXPOSURE_US=5000 rc=%x\n",e);
                }
                configured=true;
            }
            CVI_VI_ReleaseChnFrame(0,0,&frame);
        }
    }

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
