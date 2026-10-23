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
            const char page[]="HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\n\r\n<!doctype html><meta charset='utf-8'><title>LicheeRV Nano HD</title><style>body{background:#181818;color:white;text-align:center;font:18px sans-serif}img{max-width:100%;height:auto}</style><h2>1280x720 hardware MJPEG / GC4653 sensor</h2><p>Native resolution; no thumbnail upscaling. One viewer at a time.</p><img src='/live.mjpg'>";
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
            if(snapshot)break;
            if(!sendall(fd,"\r\n",2))break;
        }
        close(fd);
    }
    close(server);
}
static bool raw_sample(const VIDEO_FRAME_INFO_S& frame,const char* dir){
    char path[512];snprintf(path,sizeof(path),"%s/first-raw.nv21",dir);
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
    while(running){
        VIDEO_FRAME_INFO_S frame{};bool got=false;
        {std::lock_guard<std::mutex> guard(input_mutex);if(has_pending){frame=pending;has_pending=false;got=true;}}
        if(!got){usleep(1000);continue;}
        int e=CVI_VENC_SendFrame(0,&frame,1000);
        if(!e){
            VENC_PACK_S packets[64]{};VENC_STREAM_S stream{};stream.pstPack=packets;stream.u32PackCount=64;
            e=CVI_VENC_GetStream(0,&stream,1000);
            if(!e){
                std::vector<unsigned char> jpg;
                for(unsigned i=0;i<stream.u32PackCount;i++){const auto& p=packets[i];if(p.pu8Addr && p.u32Len>=p.u32Offset)jpg.insert(jpg.end(),p.pu8Addr+p.u32Offset,p.pu8Addr+p.u32Len);}
                CVI_VENC_ReleaseStream(0,&stream);
                if(jpg.size()<4 || jpg[0]!=0xff || jpg[1]!=0xd8)e=-1;
                else{
                    if(!encoded){char path[512];snprintf(path,sizeof(path),"%s/first-hw.jpg",dir);FILE* fp=fopen(path,"wb");if(fp){fwrite(jpg.data(),1,jpg.size(),fp);fclose(fp);}raw_sample(frame,dir);}
                    {std::lock_guard<std::mutex> guard(jpeg_mutex);latest.swap(jpg);++generation;}
                    ++encoded;
                }
            }
        }
        CVI_VI_ReleaseChnFrame(0,0,&frame);
        if(e){++errors;fprintf(stderr,"VENC encode rc=0x%x\n",e);if(errors>=5)running=0;}
    }
    std::lock_guard<std::mutex> guard(input_mutex);
    if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);has_pending=false;}
}
int main(int argc,char** argv){
    if(argc!=3 && argc!=4){fprintf(stderr,"Usage: %s USB_BIND_IP REPORT_DIR [60|80]\n",argv[0]);return 2;}
    const char* mode=argc==4?argv[3]:"80";
    if(strcmp(mode,"60") && strcmp(mode,"80"))return 2;
    setvbuf(stdout,nullptr,_IOLBF,0);signal(SIGPIPE,SIG_IGN);
    int server=socket(AF_INET,SOCK_STREAM,0);if(server<0)return 2;
    int reuse=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(8081);
    if(inet_pton(AF_INET,argv[1],&address.sin_addr)!=1 || bind(server,reinterpret_cast<sockaddr*>(&address),sizeof(address)) || listen(server,4)){perror("HTTP bind");close(server);return 2;}
    setenv("MAIX_SENSOR_FPS",mode,1);
    printf("sensor_mode=%s preview=1280x720 quality=85\n",mode);
    SAMPLE_INI_CFG_S ini{};SAMPLE_VI_CONFIG_S cfg{};
    if(SAMPLE_COMM_VI_ParseIni(&ini)||ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT){close(server);return 3;}
    ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&cfg)){close(server);return 3;}
    SIZE_S size{1280,720};if(SAMPLE_PLAT_SYS_INIT(size)){close(server);return 4;}
    if(SAMPLE_PLAT_VI_INIT(&cfg)){SAMPLE_COMM_SYS_Exit();close(server);return 5;}
    signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
    VI_CHN_ATTR_S vi{};int rc=CVI_VI_GetChnAttr(0,0,&vi);vi.u32Depth=2;if(!rc)rc=CVI_VI_SetChnAttr(0,0,&vi);
    VENC_CHN_ATTR_S attr{};
    attr.stVencAttr.enType=PT_MJPEG;
    attr.stVencAttr.u32MaxPicWidth=attr.stVencAttr.u32PicWidth=1280;
    attr.stVencAttr.u32MaxPicHeight=attr.stVencAttr.u32PicHeight=720;
    attr.stVencAttr.u32BufSize=2*1024*1024;attr.stVencAttr.bByFrame=CVI_TRUE;
    attr.stRcAttr.enRcMode=VENC_RC_MODE_MJPEGFIXQP;
    // Frames are sampled in this application; encoder input rate is not sensor rate.
    attr.stRcAttr.stMjpegFixQp.u32SrcFrameRate=30;
    attr.stRcAttr.stMjpegFixQp.fr32DstFrameRate=30;
    attr.stRcAttr.stMjpegFixQp.u32Qfactor=85;
    attr.stGopAttr.enGopMode=VENC_GOPMODE_NORMALP;
    bool created=false,receiving=false;
    if(!rc){rc=CVI_VENC_CreateChn(0,&attr);created=rc==0;printf("VENC CreateChn rc=0x%x\n",rc);}
    if(!rc){VENC_RECV_PIC_PARAM_S param{};param.s32RecvPicNum=-1;rc=CVI_VENC_StartRecvFrame(0,&param);receiving=rc==0;printf("VENC StartRecvFrame rc=0x%x\n",rc);}
    if(rc)running=0;
    std::thread server_thread(http_server,server);
    std::thread encoder_thread(encoder_worker,argv[2]);
    unsigned long count=0,dups=0,timeouts=0;uint64_t firstpts=0,lastpts=0;
    double start=now(),first=0,last=0,next=0,report=start;
    while(running){
        VIDEO_FRAME_INFO_S frame{};
        if(CVI_VI_GetChnFrame(0,0,&frame,1000)){if(running)++timeouts;continue;}
        double t=now();
        if(t-start<4){CVI_VI_ReleaseChnFrame(0,0,&frame);continue;}
        if(!count){first=t;firstpts=frame.stVFrame.u64PTS;printf("VI geometry=%ux%u stride=%u,%u format=%d\n",frame.stVFrame.u32Width,frame.stVFrame.u32Height,frame.stVFrame.u32Stride[0],frame.stVFrame.u32Stride[1],frame.stVFrame.enPixelFormat);}
        else if(frame.stVFrame.u64PTS<=lastpts)++dups;
        last=t;lastpts=frame.stVFrame.u64PTS;++count;
        bool transferred=false;
        if(t>=next){
            next=t+1.0/30;
            std::lock_guard<std::mutex> guard(input_mutex);
            if(has_pending)CVI_VI_ReleaseChnFrame(0,0,&pending);
            pending=frame;has_pending=true;transferred=true;
        }
        if(!transferred)CVI_VI_ReleaseChnFrame(0,0,&frame);
        if(t-report>=5 && count>1){printf("capture_frames=%lu host_fps=%.4f pts_fps=%.4f duplicate_pts=%lu timeouts=%lu encoded=%lu encode_errors=%lu\n",count,(count-1)/(last-first),lastpts>firstpts?(count-1)*1e6/(lastpts-firstpts):0,dups,timeouts,encoded.load(),errors.load());report=t;}
    }
    encoder_thread.join();
    server_thread.join();
    if(receiving)CVI_VENC_StopRecvFrame(0);if(created)CVI_VENC_DestroyChn(0);
    SAMPLE_COMM_VI_DestroyIsp(&cfg);SAMPLE_COMM_VI_DestroyVi(&cfg);SAMPLE_COMM_SYS_Exit();
    printf("stopped frames=%lu encoded=%lu errors=%lu\n",count,encoded.load(),errors.load());return rc||errors?1:0;
}
