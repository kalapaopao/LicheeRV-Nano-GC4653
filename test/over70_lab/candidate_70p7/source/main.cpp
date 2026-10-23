// MMF VI -> VENC MJPEG -> bounded latest JPEG -> HTTP.
// Attribute/packet conventions: official sample_common_venc.c (see PREVIEW-HD.md).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <csignal>
#include <cerrno>
#include <ctime>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <unistd.h>
#include <poll.h>
#include <sys/socket.h>
#include <arpa/inet.h>
extern "C" {
#include "sample_comm.h"
#include "cvi_venc.h"
#include "cvi_ae.h"
}
static std::atomic<int> running(1);
static_assert(ATOMIC_INT_LOCK_FREE==2,"Signal handler requires lock-free atomic int");
static std::mutex jpeg_mutex;
static std::vector<unsigned char> latest;
static unsigned long generation=0;
static std::mutex input_mutex;
static VIDEO_FRAME_INFO_S pending{};
static bool has_pending=false;
static std::atomic<unsigned long> encoded(0),errors(0);
static std::atomic<unsigned long> network_sent(0),network_bytes(0),preview_replaced(0);
static void stop(int){running=0;}
static double now(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static bool sendall(int fd,const void* ptr,size_t n){
    const char* p=static_cast<const char*>(ptr);
    while(running && n){ssize_t r=send(fd,p,n,MSG_NOSIGNAL);if(r>0){p+=r;n-=r;}else if(r<0 && errno==EINTR)continue;else return false;}
    return !n;
}
static void http_server(int server){
    while(running){
        pollfd p{server,POLLIN,0};if(poll(&p,1,100)<=0)continue;
        int fd=accept(server,nullptr,nullptr);if(fd<0)continue;
        timeval timeout{1,0};setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
        int sndbuf=128*1024;setsockopt(fd,SOL_SOCKET,SO_SNDBUF,&sndbuf,sizeof(sndbuf));
        char request[4096]{};ssize_t n=recv(fd,request,sizeof(request)-1,0);
        if(n<=0){close(fd);continue;}
        bool snapshot=strstr(request,"GET /snapshot.jpg ")==request;
        bool stream=strstr(request,"GET /live.mjpg ")==request;
        if(!snapshot && !stream){
            const char page[]="HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\n\r\n<!doctype html><meta charset='utf-8'><title>LicheeRV Nano HD</title><style>body{background:#181818;color:white;text-align:center;font:18px sans-serif}img{max-width:100%;height:auto}</style><h2>1920x1080 hardware MJPEG / GC4653 sensor</h2><p>Native resolution; no thumbnail upscaling. One viewer at a time.</p><img src='/live.mjpg'>";
            sendall(fd,page,sizeof(page)-1);close(fd);continue;
        }
        unsigned long seen=0;
        if(stream){const char hdr[]="HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\nCache-Control: no-store, no-cache\r\nPragma: no-cache\r\nConnection: close\r\n\r\n";if(!sendall(fd,hdr,sizeof(hdr)-1)){close(fd);continue;}}
        while(running){
            std::vector<unsigned char> jpg;
            {std::lock_guard<std::mutex> guard(jpeg_mutex);if(generation!=seen){seen=generation;jpg=latest;}}
            if(jpg.empty()){usleep(2000);continue;}
            char hdr[256];
            int count=snprintf(hdr,sizeof(hdr),snapshot?"HTTP/1.0 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\nCache-Control: no-store\r\n\r\n":"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",jpg.size());
            if(!sendall(fd,hdr,count)||!sendall(fd,jpg.data(),jpg.size()))break;
            ++network_sent;network_bytes+=jpg.size();
            if(snapshot)break;
            if(!sendall(fd,"\r\n",2))break;
        }
        close(fd);
    }
    close(server);
}
static bool raw_sample(const VIDEO_FRAME_INFO_S& frame,const char* dir,int sample_id){
    char path[512];snprintf(path,sizeof(path),"%s/raw-%d.nv21",dir,sample_id);
    FILE* fp=fopen(path,"wb");if(!fp)return false;bool ok=true;
    const auto& v=frame.stVFrame;
    for(int p=0;p<2;p++){
        size_t size=v.u32Stride[p]*(p?v.u32Height/2:v.u32Height);
        void* addr=CVI_SYS_MmapCache(v.u64PhyAddr[p],size);
        if(!addr){ok=false;break;}
        if(CVI_SYS_IonInvalidateCache(v.u64PhyAddr[p],addr,size))ok=false;
        for(unsigned y=0;y<(p?v.u32Height/2:v.u32Height);y++)if(fwrite(static_cast<char*>(addr)+y*v.u32Stride[p],1,v.u32Width,fp)!=v.u32Width)ok=false;
        CVI_SYS_Munmap(addr,size);
    }
    fclose(fp);return ok;
}
static void encoder_worker(const char* dir){
    int sampled=0;
    double next_sample=0;
    int sample_limit=3;
    double sample_interval=4;
    if(const char* v=getenv("LAB_RAW_LIMIT")){
        if(!strcmp(v,"6"))sample_limit=6;
    }
    if(const char* v=getenv("LAB_RAW_INTERVAL_S")){
        if(!strcmp(v,"15"))sample_interval=15;
    }
    while(running){
        VIDEO_FRAME_INFO_S frame{};bool got=false;
        {std::lock_guard<std::mutex> guard(input_mutex);if(has_pending){frame=pending;has_pending=false;got=true;}}
        if(!got){usleep(1000);continue;}
        VENC_RECV_PIC_PARAM_S receive{};receive.s32RecvPicNum=1;
        int e=CVI_VENC_StartRecvFrame(0,&receive);
        if(!e)e=CVI_VENC_SendFrame(0,&frame,1000);
        if(!e){
            VENC_PACK_S packets[64]{};VENC_STREAM_S stream{};stream.pstPack=packets;stream.u32PackCount=64;
            e=CVI_VENC_GetStream(0,&stream,1000);
            if(!e){
                std::vector<unsigned char> jpg;
                for(unsigned i=0;i<stream.u32PackCount;i++){const auto& p=packets[i];if(p.pu8Addr && p.u32Len>=p.u32Offset)jpg.insert(jpg.end(),p.pu8Addr+p.u32Offset,p.pu8Addr+p.u32Len);}
                CVI_VENC_ReleaseStream(0,&stream);
                if(jpg.size()<4 || jpg[0]!=0xff || jpg[1]!=0xd8)e=-1;
                else{
                    if(!encoded){char path[512];snprintf(path,sizeof(path),"%s/first-hw.jpg",dir);FILE* fp=fopen(path,"wb");if(fp){fwrite(jpg.data(),1,jpg.size(),fp);fclose(fp);}}
                    if(sampled<sample_limit && now()>=next_sample){
                        bool ok=raw_sample(frame,dir,sampled);
                        printf("LAB_NV21_SAMPLE id=%d ok=%d\n",sampled,ok?1:0);
                        if(!ok)++errors;
                        ++sampled;
                        next_sample=now()+sample_interval;
                    }
                    {std::lock_guard<std::mutex> guard(jpeg_mutex);latest.swap(jpg);++generation;}
                    ++encoded;
                }
            }
        }
        CVI_VENC_StopRecvFrame(0);
        CVI_VI_ReleaseChnFrame(0,0,&frame);
        if(e){++errors;fprintf(stderr,"VENC encode rc=0x%x\n",e);if(errors>=5)running=0;}
    }
    std::lock_guard<std::mutex> guard(input_mutex);
    if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);has_pending=false;}
}
int main(int argc,char** argv){
    if(argc!=3 && argc!=4){fprintf(stderr,"Usage: %s USB_BIND_IP REPORT_DIR [60]\n",argv[0]);return 2;}
    const char* mode=argc==4?argv[3]:"60";
    if(strcmp(mode,"60"))return 2;
    int quality=90;
    if(const char* value=getenv("PREVIEW_FACTORY_QUALITY")){char* end=nullptr;long q=strtol(value,&end,10);if(!*value || *end || q<85 || q>95){fprintf(stderr,"PREVIEW_FACTORY_QUALITY must be 85..95\n");return 2;}quality=q;}
    setvbuf(stdout,nullptr,_IOLBF,0);signal(SIGPIPE,SIG_IGN);
    int server=socket(AF_INET,SOCK_STREAM,0);if(server<0)return 2;
    int reuse=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(8081);
    if(inet_pton(AF_INET,argv[1],&address.sin_addr)!=1 || bind(server,reinterpret_cast<sockaddr*>(&address),sizeof(address)) || listen(server,4)){perror("HTTP bind");close(server);return 2;}
    setenv("MAIX_SENSOR_FPS",mode,1);
    printf("sensor_mode=%s preview=1920x1080 quality=%d preview_limiter=none\n",mode,quality);
    SAMPLE_INI_CFG_S ini{};SAMPLE_VI_CONFIG_S cfg{};
    if(SAMPLE_COMM_VI_ParseIni(&ini)||ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT){close(server);return 3;}
    ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&cfg)){close(server);return 3;}
    SIZE_S size{1920,1080};if(SAMPLE_PLAT_SYS_INIT(size)){close(server);return 4;}
    if(SAMPLE_PLAT_VI_INIT(&cfg)){SAMPLE_COMM_SYS_Exit();close(server);return 5;}
    signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
    VI_CHN_ATTR_S vi{};int rc=CVI_VI_GetChnAttr(0,0,&vi);vi.u32Depth=2;if(!rc)rc=CVI_VI_SetChnAttr(0,0,&vi);
    VENC_CHN_ATTR_S attr{};
    // JPEG single-frame mode has no MJPEG frame-rate-control field.
    attr.stVencAttr.enType=PT_JPEG;
    attr.stVencAttr.u32MaxPicWidth=attr.stVencAttr.u32PicWidth=1920;
    attr.stVencAttr.u32MaxPicHeight=attr.stVencAttr.u32PicHeight=1080;
    attr.stVencAttr.u32BufSize=2*1024*1024;attr.stVencAttr.bByFrame=CVI_TRUE;
    attr.stVencAttr.stAttrJpege.bSupportDCF=CVI_FALSE;
    attr.stVencAttr.stAttrJpege.stMPFCfg.u8LargeThumbNailNum=0;
    attr.stVencAttr.stAttrJpege.enReceiveMode=VENC_PIC_RECEIVE_SINGLE;
    attr.stGopAttr.enGopMode=VENC_GOPMODE_NORMALP;
    bool created=false;
    if(!rc){rc=CVI_VENC_CreateChn(0,&attr);created=rc==0;printf("VENC CreateChn rc=0x%x\n",rc);}
    if(!rc){VENC_JPEG_PARAM_S jpeg{};rc=CVI_VENC_GetJpegParam(0,&jpeg);if(!rc){jpeg.u32Qfactor=quality;rc=CVI_VENC_SetJpegParam(0,&jpeg);}printf("VENC JPEG quality rc=0x%x\n",rc);}
    if(rc)running=0;
    std::thread server_thread(http_server,server);
    std::thread encoder_thread(encoder_worker,argv[2]);
    unsigned long count=0,dups=0,timeouts=0;uint64_t firstpts=0,lastpts=0;
    double start=now(),first=0,last=0,report=start;
    bool fps_applied=false;
    unsigned long last_encoded=0,last_sent=0,last_bytes=0;
    while(running){
        VIDEO_FRAME_INFO_S frame{};
        if(CVI_VI_GetChnFrame(0,0,&frame,1000)){if(running)++timeouts;continue;}
        double t=now();
        if(!fps_applied && t-start>=2){
            fps_applied=true;
            ISP_PUB_ATTR_S pub{};int e=CVI_ISP_GetPubAttr(0,&pub);
            printf("factory original ISP FPS=%f rc=%x\n",pub.f32FrameRate,e);
            if(!e){pub.f32FrameRate=60;printf("factory set ISP FPS rc=%x\n",CVI_ISP_SetPubAttr(0,&pub));}
            ISP_EXPOSURE_ATTR_S ae{};e=CVI_ISP_GetExposureAttr(0,&ae);
            if(!e){ae.enOpType=OP_TYPE_AUTO;ae.stAuto.enAEMode=AE_MODE_FIX_FRAME_RATE;ae.stAuto.stExpTimeRange.u32Max=12000;printf("factory fixed-rate AE max12000us rc=%x\n",CVI_ISP_SetExposureAttr(0,&ae));}
        }
        if(t-start<4){CVI_VI_ReleaseChnFrame(0,0,&frame);continue;}
        if(!count){first=t;firstpts=frame.stVFrame.u64PTS;printf("VI geometry=%ux%u stride=%u,%u format=%d\n",frame.stVFrame.u32Width,frame.stVFrame.u32Height,frame.stVFrame.u32Stride[0],frame.stVFrame.u32Stride[1],frame.stVFrame.enPixelFormat);}
        else if(frame.stVFrame.u64PTS<=lastpts)++dups;
        last=t;lastpts=frame.stVFrame.u64PTS;++count;
        {
            std::lock_guard<std::mutex> guard(input_mutex);
            if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);++preview_replaced;}
            pending=frame;has_pending=true;
        }
        if(t-report>=5 && count>1){
            unsigned long enc=encoded.load(),sent=network_sent.load(),bytes=network_bytes.load();
            printf("capture_frames=%lu host_fps=%.4f pts_fps=%.4f duplicate_pts=%lu timeouts=%lu encoded=%lu encode_errors=%lu encode_fps=%.3f sent_fps=%.3f jpeg_mbit_s=%.3f preview_replaced=%lu\n",count,(count-1)/(last-first),lastpts>firstpts?(count-1)*1e6/(lastpts-firstpts):0,dups,timeouts,enc,errors.load(),(enc-last_encoded)/(t-report),(sent-last_sent)/(t-report),(bytes-last_bytes)*8e-6/(t-report),preview_replaced.load());
            last_encoded=enc;last_sent=sent;last_bytes=bytes;report=t;
        }
    }
    encoder_thread.join();
    {std::lock_guard<std::mutex> guard(input_mutex);if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);has_pending=false;}}
    server_thread.join();
    if(created){CVI_VENC_StopRecvFrame(0);CVI_VENC_DestroyChn(0);}
    SAMPLE_COMM_VI_DestroyIsp(&cfg);SAMPLE_COMM_VI_DestroyVi(&cfg);SAMPLE_COMM_SYS_Exit();
    printf("stopped frames=%lu encoded=%lu errors=%lu\n",count,encoded.load(),errors.load());return rc||errors?1:0;
}
