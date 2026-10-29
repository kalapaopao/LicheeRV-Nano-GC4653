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
#include "record80.h"
#include <poll.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include "cviruntime.h"
extern "C" {
#include "sample_comm.h"
#include "cvi_venc.h"
#include "cvi_isp.h"
#include "cvi_ae.h"
}
static bool env_u32(const char* name,unsigned fallback,unsigned low,unsigned high,unsigned& out){
    const char* s=getenv(name);if(!s){out=fallback;return true;}
    if(!*s)return false;
    errno=0;char* end=nullptr;unsigned long v=strtoul(s,&end,10);
    if(errno || *end || v<low || v>high)return false;
    out=static_cast<unsigned>(v);return true;
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
static std::atomic<unsigned long> inference_done(0),inference_errors(0),inference_ms(0);
static std::atomic<int> save_after_jpeg_request(0);
static MJPEGRecorder recorder("/code/camera/recordings");
class FlyRmNpu {
    CVI_MODEL_HANDLE model_=nullptr; CVI_TENSOR *input_=nullptr,*output_=nullptr; int32_t in_n_=0,out_n_=0;
    std::atomic<int> ready_{0},busy_{0};
public:
    bool open(const char* path){
        if(CVI_NN_RegisterModel(path,&model_)!=0)return false;
        if(CVI_NN_GetInputOutputTensors(model_,&input_,&in_n_,&output_,&out_n_)!=0 || in_n_<1 || out_n_<1)return false;
        input_[0].pixel_format=CVI_NN_PIXEL_YUV_NV21; input_[0].mean[0]=input_[0].mean[1]=input_[0].mean[2]=0.f;
        input_[0].scale[0]=input_[0].scale[1]=input_[0].scale[2]=1.f; return true;
    }
    bool prepare(const VIDEO_FRAME_INFO_S& frame){
        if(!model_ || !input_ || !output_)return false;
        if(busy_.load(std::memory_order_acquire) || ready_.load(std::memory_order_acquire))return false;
        uint64_t addr[1]={frame.stVFrame.u64PhyAddr[0]};
        if(CVI_NN_SetTensorWithAlignedFrames(input_,addr,1,CVI_NN_PIXEL_YUV_NV21)!=0)return false;
        ready_.store(1,std::memory_order_release); return true;
    }
    bool run_once(){
        if(busy_.exchange(1,std::memory_order_acq_rel))return false;
        if(!ready_.exchange(0,std::memory_order_acquire)){busy_.store(0,std::memory_order_release);return false;}
        bool ok=CVI_NN_Forward(model_,input_,in_n_,output_,out_n_)==0;
        busy_.store(0,std::memory_order_release); return ok;
    }
    ~FlyRmNpu(){if(model_)CVI_NN_CleanupModel(model_);}
};
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
            const char page[]=R"PAGE(HTTP/1.0 200 OK
Content-Type: text/html; charset=utf-8
Cache-Control: no-store

<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GC4653 80FPS 录像采集</title><style>
body{margin:0;background:#101827;color:#edf4ff;font:15px "Microsoft Yahei",sans-serif}
main{max-width:1250px;margin:auto;padding:20px}
h2{font-size:22px}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}
button{border:0;border-radius:8px;color:#fff;background:#276b58;padding:12px 20px;font-size:15px;cursor:pointer}
button.stop{background:#a83d48}button:disabled{opacity:.4}
#status{color:#9de6d5}#view{width:100%;height:auto;background:black;border-radius:8px}
small{color:#a6bdcf;display:block;line-height:1.8}
</style><main><h2>GC4653 · 1280×720 · 80FPS 采集 / 40FPS Q85 录像</h2>
<div class="toolbar"><button id="start" onclick="cmd('start')" disabled>● 开始录像</button>
<button id="stop" class="stop" onclick="cmd('stop')" disabled>■ 停止录像</button>
<button id="reconnect" onclick="location.reload()" hidden>重新连接</button>
<span id="status">正在连接录像控制服务…</span></div>
<img id="view" src="/live.mjpg"><p id="detail"></p>
<small>录像格式 MJPEG AVI，记录每2帧中的1帧（40FPS），原始取流维持80FPS，无二次 JPEG 编码。录像在板端 /code/camera/recordings，每段最多60秒。视频 FPS 以实际文件解码检测为准。网页显示速率不等于摄像头采集速率。</small>
<script>
const api='http://'+location.hostname+':8082';
let disconnected=false,pollTimer=null,refreshBusy=false;
const requests=new Set();
function offline(reason){if(disconnected)return;disconnected=true;clearTimeout(pollTimer);
for(const controller of requests)controller.abort();
document.getElementById('start').disabled=true;document.getElementById('stop').disabled=true;
document.getElementById('reconnect').hidden=false;document.getElementById('view').remove();
document.getElementById('status').textContent='连接已断开，已停止自动请求';
document.getElementById('detail').textContent=reason+'。请确认摄像头已启动，再点击“重新连接”。';}
async function request(path,options){const controller=new AbortController();requests.add(controller);
const timeout=setTimeout(()=>controller.abort(),3000);
try{const r=await fetch(api+path,{...options,signal:controller.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json();}
finally{clearTimeout(timeout);requests.delete(controller);}}
async function cmd(action){if(disconnected)return;try{await request('/'+action,{method:'POST'});if(!disconnected)await refresh();}
catch(e){offline('录像控制请求失败：'+e.message);}}
async function refresh(){if(disconnected||refreshBusy)return;clearTimeout(pollTimer);refreshBusy=true;
try{const d=await request('/status',{cache:'no-store'});if(disconnected)return;document.getElementById('start').disabled=d.requested;
document.getElementById('stop').disabled=!d.requested;document.getElementById('status').textContent=d.recording?'● 正在录制：'+d.file:(d.requested?'准备中':'未录像');
document.getElementById('detail').textContent='已录编码帧：'+d.written+' · 队列丢帧：'+d.dropped+' · 输出：'+(d.bytes/1048576).toFixed(1)+' MB · 已完成：'+d.segments+'段 · '+(d.error||'正常');
}catch(e){offline('摄像头服务或网络不可用：'+e.message);}
finally{refreshBusy=false;if(!disconnected)pollTimer=setTimeout(refresh,1000);}}
document.getElementById('view').addEventListener('error',()=>offline('预览连接中断'));
window.addEventListener('pagehide',()=>offline('页面已关闭'));
refresh();
</script></main></html>)PAGE";
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
static void record_control_server(const char* bind_ip){
    int srv=socket(AF_INET,SOCK_STREAM,0);
    if(srv<0){fprintf(stderr,"RECORD_CONTROL_SOCKET_FAILED\n");return;}
    int reuse=1;setsockopt(srv,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
    sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(8082);
    if(inet_pton(AF_INET,bind_ip,&addr.sin_addr)!=1 ||
       bind(srv,(sockaddr*)&addr,sizeof(addr))!=0 || listen(srv,8)!=0){
        perror("RECORD_CONTROL_BIND");close(srv);return;
    }
    printf("RECORD_CONTROL_READY http://%s:8082/status\n",bind_ip);
    while(running){
        pollfd p{srv,POLLIN,0};if(poll(&p,1,120)<=0)continue;
        int fd=accept(srv,nullptr,nullptr);if(fd<0)continue;
        timeval tv{2,0};
        setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
        setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&tv,sizeof(tv));
        char request[1024]{};
        if(recv(fd,request,sizeof(request)-1,0)<=0){close(fd);continue;}
        char method[12]{},route[128]{};
        sscanf(request,"%11s %127s",method,route);
        std::string body;
        const char* status="200 OK";
        if(strcmp(method,"OPTIONS")==0)body="{}";
        else if(strcmp(method,"POST")==0 && strcmp(route,"/start")==0){
            recorder.command(true);body="{\"accepted\":true,\"action\":\"start\"}";
        }else if(strcmp(method,"POST")==0 && strcmp(route,"/stop")==0){
            recorder.command(false);body="{\"accepted\":true,\"action\":\"stop\"}";
        }else if(strcmp(method,"GET")==0 && strcmp(route,"/status")==0)
            body=recorder.status();
        else {status="404 Not Found";body="{\"error\":\"route not found\"}";}
        char hdr[512];
        int k=snprintf(hdr,sizeof(hdr),"HTTP/1.1 %s\r\nContent-Type: application/json\r\n"
           "Content-Length: %zu\r\nAccess-Control-Allow-Origin: *\r\n"
           "Access-Control-Allow-Methods: GET,POST,OPTIONS\r\n"
           "Access-Control-Allow-Headers: Content-Type\r\nConnection: close\r\n\r\n",status,body.size());
        if(k>0&&k<(int)sizeof(hdr))sendall(fd,hdr,k);
        sendall(fd,body.data(),body.size());
        close(fd);
    }
    close(srv);
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
static void bayer_sample(const char* dir,const char* phase){
    VI_DUMP_ATTR_S previous{},dump{};int e=CVI_VI_GetPipeDumpAttr(0,&previous);
    if(e){printf("DIAG GetPipeDump=%x\n",e);return;}
    dump.bEnable=CVI_TRUE;dump.u32Depth=1;dump.enDumpType=VI_DUMP_TYPE_RAW;
    e=CVI_VI_SetPipeDumpAttr(0,&dump);printf("DIAG SetPipeDump=%x\n",e);
    if(!e){
        VIDEO_FRAME_INFO_S f[2]{};e=CVI_VI_GetPipeFrame(0,f,1000);printf("DIAG GetPipeFrame=%x\n",e);
        if(!e){
            const auto& v=f[0].stVFrame;
            printf("DIAG BAYER width=%u height=%u stride=%u length=%u pixel=%d compress=%d bayer=%d\n",v.u32Width,v.u32Height,v.u32Stride[0],v.u32Length[0],v.enPixelFormat,v.enCompressMode,v.enBayerFormat);
            if(v.u32Length[0] && v.u32Length[0]<64*1024*1024){
                void* p=CVI_SYS_MmapCache(v.u64PhyAddr[0],v.u32Length[0]);
                if(p){CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0],p,v.u32Length[0]);char path[512];snprintf(path,sizeof(path),"%s/sensor-bayer-%s.bin",dir,phase);FILE* fp=fopen(path,"wb");if(fp){fwrite(p,1,v.u32Length[0],fp);fclose(fp);}CVI_SYS_Munmap(p,v.u32Length[0]);}
            }
            CVI_VI_ReleasePipeFrame(0,f);
        }
        printf("DIAG restore PipeDump=%x\n",CVI_VI_SetPipeDumpAttr(0,&previous));
    }
}
static void encoder_worker(const char* dir){
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
                    if(!encoded){char path[512];snprintf(path,sizeof(path),"%s/first-hw.jpg",dir);FILE* fp=fopen(path,"wb");if(fp){fwrite(jpg.data(),1,jpg.size(),fp);fclose(fp);}raw_sample(frame,dir);}
                    if(save_after_jpeg_request.load()==1 && save_after_jpeg_request.exchange(2)==1){char path[512];snprintf(path,sizeof(path),"%s/after-hw.jpg",dir);FILE* fp=fopen(path,"wb");if(fp){fwrite(jpg.data(),1,jpg.size(),fp);fclose(fp);}}
                    if(save_after_jpeg_request.load()==3 && save_after_jpeg_request.exchange(4)==3){char path[512];snprintf(path,sizeof(path),"%s/late-hw.jpg",dir);FILE* fp=fopen(path,"wb");if(fp){fwrite(jpg.data(),1,jpg.size(),fp);fclose(fp);}}
                    // Preserve 80 FPS acquisition/preview; archive every second encoded frame at the configured JPEG quality.
                    if((encoded.load()&1ul)==0) recorder.push(jpg);
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
    if(argc!=3 && argc!=4){fprintf(stderr,"Usage: %s USB_BIND_IP REPORT_DIR [60|80]\n",argv[0]);return 2;}
    const char* mode="80";
    if(argc==4 && strcmp(argv[3],"80"))return 2;
    const char* exposure_mode=getenv("RECORD80_EXPOSURE_MODE");
    if(!exposure_mode)exposure_mode="auto";
    if(strcmp(exposure_mode,"auto") && strcmp(exposure_mode,"manual")){fprintf(stderr,"Invalid exposure mode\n");return 2;}
    const char* blc_mode=getenv("RECORD80_BLC_MODE");
    if(!blc_mode)blc_mode="default";
    if(strcmp(blc_mode,"default") && strcmp(blc_mode,"manual")){fprintf(stderr,"Invalid black level mode\n");return 2;}
    unsigned blc_r,blc_gr,blc_gb,blc_b;
    if(!env_u32("RECORD80_BLC_R",256,0,4095,blc_r) ||
       !env_u32("RECORD80_BLC_GR",256,0,4095,blc_gr) ||
       !env_u32("RECORD80_BLC_GB",256,0,4095,blc_gb) ||
       !env_u32("RECORD80_BLC_B",256,0,4095,blc_b)){
        fprintf(stderr,"Invalid RECORD80 black level value\n");return 2;
    }
    unsigned quality,auto_exp,auto_again,auto_dgain,auto_ispgain,manual_exp,manual_again,manual_dgain,manual_ispgain;
    if(!env_u32("RECORD80_JPEG_QUALITY",85,75,90,quality) ||
       !env_u32("RECORD80_AUTO_EXP_MAX_US",0,0,10000,auto_exp) ||
       !env_u32("RECORD80_AUTO_AGAIN_MAX",0,0,16384,auto_again) ||
       !env_u32("RECORD80_AUTO_DGAIN_MAX",0,0,4096,auto_dgain) ||
       !env_u32("RECORD80_AUTO_ISPGAIN_MAX",0,0,4096,auto_ispgain) ||
       !env_u32("RECORD80_MANUAL_EXP_US",5000,100,10000,manual_exp) ||
       !env_u32("RECORD80_MANUAL_AGAIN",1024,1024,16384,manual_again) ||
       !env_u32("RECORD80_MANUAL_DGAIN",1024,1024,4096,manual_dgain) ||
       !env_u32("RECORD80_MANUAL_ISPGAIN",1024,1024,4096,manual_ispgain) ||
       (auto_again && auto_again<1024) || (auto_dgain && auto_dgain<1024) ||
       (auto_ispgain && auto_ispgain<1024)){
        fprintf(stderr,"Invalid RECORD80 tuning value\n");return 2;
    }
    setvbuf(stdout,nullptr,_IOLBF,0);signal(SIGPIPE,SIG_IGN);
    FlyRmNpu npu; const char* model_path=getenv("FLY_RM_MODEL");
    if(model_path && *model_path){
        if(!npu.open(model_path)){fprintf(stderr,"FLY_RM_MODEL_OPEN_FAILED path=%s\n",model_path);return 6;}
        printf("FLY_RM_MODEL_READY path=%s input=320x320 format=NV21\n",model_path);
    }
    int server=socket(AF_INET,SOCK_STREAM,0);if(server<0)return 2;
    int reuse=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&reuse,sizeof(reuse));
    sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(8081);
    if(inet_pton(AF_INET,argv[1],&address.sin_addr)!=1 || bind(server,reinterpret_cast<sockaddr*>(&address),sizeof(address)) || listen(server,4)){perror("HTTP bind");close(server);return 2;}
    setenv("MAIX_SENSOR_FPS",mode,1);
    printf("sensor_mode=%s preview=1280x720 quality=%u preview_limiter=none exposure_mode=%s\n",mode,quality,exposure_mode);
    printf("RECORD80_BLC_CONFIG mode=%s offsets=%u,%u,%u,%u\n",blc_mode,blc_r,blc_gr,blc_gb,blc_b);
    SAMPLE_INI_CFG_S ini{};SAMPLE_VI_CONFIG_S cfg{};
    if(SAMPLE_COMM_VI_ParseIni(&ini)||ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT){close(server);return 3;}
    ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&cfg)){close(server);return 3;}
    if(getenv("PREVIEW_DIAG_LINEAR"))cfg.astViInfo[0].stChnInfo.enCompressMode=COMPRESS_MODE_NONE;
    printf("DIAG configured_compress=%d\n",cfg.astViInfo[0].stChnInfo.enCompressMode);
    SIZE_S size{1280,720};if(SAMPLE_PLAT_SYS_INIT(size)){close(server);return 4;}
    if(SAMPLE_PLAT_VI_INIT(&cfg)){SAMPLE_COMM_SYS_Exit();close(server);return 5;}
    signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGPIPE,SIG_IGN);
    VI_CHN_ATTR_S vi{};int rc=CVI_VI_GetChnAttr(0,0,&vi);vi.u32Depth=2;if(!rc)rc=CVI_VI_SetChnAttr(0,0,&vi);
    VI_PIPE_ATTR_S pipe{};int prc=CVI_VI_GetPipeAttr(0,&pipe);
    printf("DIAG channel_rc=%x compress=%d video=%d depth=%u pipe_rc=%x pipe_compress=%d\n",rc,vi.enCompressMode,vi.enVideoFormat,vi.u32Depth,prc,pipe.enCompressMode);
    VENC_CHN_ATTR_S attr{};
    // JPEG single-frame mode has no MJPEG frame-rate-control field.
    attr.stVencAttr.enType=PT_JPEG;
    attr.stVencAttr.u32MaxPicWidth=attr.stVencAttr.u32PicWidth=1280;
    attr.stVencAttr.u32MaxPicHeight=attr.stVencAttr.u32PicHeight=720;
    attr.stVencAttr.u32BufSize=2*1024*1024;attr.stVencAttr.bByFrame=CVI_TRUE;
    attr.stVencAttr.stAttrJpege.bSupportDCF=CVI_FALSE;
    attr.stVencAttr.stAttrJpege.stMPFCfg.u8LargeThumbNailNum=0;
    attr.stVencAttr.stAttrJpege.enReceiveMode=VENC_PIC_RECEIVE_SINGLE;
    attr.stGopAttr.enGopMode=VENC_GOPMODE_NORMALP;
    bool created=false;
    if(!rc){rc=CVI_VENC_CreateChn(0,&attr);created=rc==0;printf("VENC CreateChn rc=0x%x\n",rc);}
    if(!rc){VENC_JPEG_PARAM_S jpeg{};rc=CVI_VENC_GetJpegParam(0,&jpeg);if(!rc){jpeg.u32Qfactor=quality;rc=CVI_VENC_SetJpegParam(0,&jpeg);}printf("VENC JPEG quality=%u rc=0x%x\n",quality,rc);}
    if(rc)running=0;
    recorder.launch();
    if(getenv("RECORD_AUTOSTART") && strcmp(getenv("RECORD_AUTOSTART"),"1")==0)recorder.command(true);
    std::thread server_thread(http_server,server);
    std::thread control_thread(record_control_server,argv[1]);
    std::thread encoder_thread(encoder_worker,argv[2]);
    std::thread infer_thread;
    if(model_path && *model_path){
        infer_thread=std::thread([&](){while(running){double s=now();if(npu.run_once()){++inference_done;inference_ms+=static_cast<unsigned long>((now()-s)*1000.0);}else usleep(500);}});
    }
    unsigned long count=0,dups=0,timeouts=0;uint64_t firstpts=0,lastpts=0;
    double start=now(),first=0,last=0,report=start;
    bool diag_applied=false;bool later_sample_done=false;bool last_sample_done=false;
    bool tuning_failed=false;bool blc_check_done=false;double last_ae_report=0;
    unsigned long last_encoded=0,last_sent=0,last_bytes=0,last_frame_count=0;uint64_t last_window_pts=0;
    while(running){
        VIDEO_FRAME_INFO_S frame{};
        if(CVI_VI_GetChnFrame(0,0,&frame,1000)){if(running)++timeouts;continue;}
        double t=now();
        if(!diag_applied && t-start>2){
            diag_applied=true;
            ISP_EXPOSURE_ATTR_S ae{};int ae_rc=CVI_ISP_GetExposureAttr(0,&ae);
            printf("RECORD80_AE_BEFORE rc=0x%x mode=%d exp_min=%u exp_max=%u\n",ae_rc,ae.enOpType,ae.stAuto.stExpTimeRange.u32Min,ae.stAuto.stExpTimeRange.u32Max);
            if(!ae_rc && !strcmp(exposure_mode,"manual")){
                ae.enOpType=OP_TYPE_MANUAL;ae.stManual.enGainType=AE_TYPE_GAIN;
                ae.stManual.enExpTimeOpType=ae.stManual.enAGainOpType=ae.stManual.enDGainOpType=ae.stManual.enISPDGainOpType=OP_TYPE_MANUAL;
                ae.stManual.u32ExpTime=manual_exp;ae.stManual.u32AGain=manual_again;
                ae.stManual.u32DGain=manual_dgain;ae.stManual.u32ISPDGain=manual_ispgain;
                ae_rc=CVI_ISP_SetExposureAttr(0,&ae);
                printf("RECORD80_AE_MANUAL exp_us=%u again=%u dgain=%u isp_gain=%u rc=0x%x\n",manual_exp,manual_again,manual_dgain,manual_ispgain,ae_rc);
            }else if(!ae_rc && (auto_exp||auto_again||auto_dgain||auto_ispgain)){
                ae.enOpType=OP_TYPE_AUTO;
                if(auto_exp){ae.stAuto.stExpTimeRange.u32Max=auto_exp;if(ae.stAuto.stExpTimeRange.u32Min>auto_exp)ae.stAuto.stExpTimeRange.u32Min=auto_exp;}
                if(auto_again){ae.stAuto.stAGainRange.u32Max=auto_again;if(ae.stAuto.stAGainRange.u32Min>auto_again)ae.stAuto.stAGainRange.u32Min=auto_again;}
                if(auto_dgain){ae.stAuto.stDGainRange.u32Max=auto_dgain;if(ae.stAuto.stDGainRange.u32Min>auto_dgain)ae.stAuto.stDGainRange.u32Min=auto_dgain;}
                if(auto_ispgain){ae.stAuto.stISPDGainRange.u32Max=auto_ispgain;if(ae.stAuto.stISPDGainRange.u32Min>auto_ispgain)ae.stAuto.stISPDGainRange.u32Min=auto_ispgain;}
                ae_rc=CVI_ISP_SetExposureAttr(0,&ae);
                printf("RECORD80_AE_AUTO_LIMIT exp_max=%u again_max=%u dgain_max=%u isp_gain_max=%u rc=0x%x\n",auto_exp,auto_again,auto_dgain,auto_ispgain,ae_rc);
            }
            if(ae_rc && (!strcmp(exposure_mode,"manual") || auto_exp || auto_again || auto_dgain || auto_ispgain)){
                tuning_failed=true;running=0;
            }
            if(!strcmp(blc_mode,"manual")){
                ISP_BLACK_LEVEL_ATTR_S blc{};int be=CVI_ISP_GetBlackLevelAttr(0,&blc);
                if(!be){
                    blc.Enable=CVI_TRUE;blc.enOpType=OP_TYPE_MANUAL;
                    blc.stManual.OffsetR=blc_r;blc.stManual.OffsetGr=blc_gr;
                    blc.stManual.OffsetGb=blc_gb;blc.stManual.OffsetB=blc_b;
                    be=CVI_ISP_SetBlackLevelAttr(0,&blc);
                }
                bool match=false;
                if(!be){
                    ISP_BLACK_LEVEL_ATTR_S readback{};be=CVI_ISP_GetBlackLevelAttr(0,&readback);
                    match=!be && readback.Enable && readback.enOpType==OP_TYPE_MANUAL &&
                        readback.stManual.OffsetR==blc_r && readback.stManual.OffsetGr==blc_gr &&
                        readback.stManual.OffsetGb==blc_gb && readback.stManual.OffsetB==blc_b;
                }
                printf("RECORD80_BLC_SET offsets=%u,%u,%u,%u rc=0x%x readback_match=%d\n",blc_r,blc_gr,blc_gb,blc_b,be,match);
                if(be || !match){tuning_failed=true;running=0;}
            }
            ISP_PUB_ATTR_S pub{};int pe=CVI_ISP_GetPubAttr(0,&pub);printf("DIAG ISP pub fps=%f get=%x\n",pub.f32FrameRate,pe);
            if(!pe && getenv("PREVIEW_DIAG_PUBFPS")){pub.f32FrameRate=atof(getenv("PREVIEW_DIAG_PUBFPS"));printf("DIAG set ISP pub fps=%f rc=%x\n",pub.f32FrameRate,CVI_ISP_SetPubAttr(0,&pub));}
            if(getenv("PREVIEW_DIAG_RAW"))bayer_sample(argv[2],"before");
            if(getenv("PREVIEW_DIAG_NOTNR")){ISP_TNR_ATTR_S a{};int e=CVI_ISP_GetTNRAttr(0,&a);printf("DIAG TNR enabled=%d get=%x\n",a.Enable,e);if(!e){a.Enable=CVI_FALSE;printf("DIAG disable TNR=%x\n",CVI_ISP_SetTNRAttr(0,&a));}}
            if(getenv("PREVIEW_DIAG_NODPC")){ISP_DP_DYNAMIC_ATTR_S a{};ISP_DP_STATIC_ATTR_S b{};int e=CVI_ISP_GetDPDynamicAttr(0,&a);printf("DIAG DPC dynamic=%d get=%x\n",a.Enable,e);if(!e){a.Enable=CVI_FALSE;printf("DIAG disable dynamicDPC=%x\n",CVI_ISP_SetDPDynamicAttr(0,&a));}e=CVI_ISP_GetDPStaticAttr(0,&b);printf("DIAG DPC static=%d get=%x\n",b.Enable,e);if(!e){b.Enable=CVI_FALSE;printf("DIAG disable staticDPC=%x\n",CVI_ISP_SetDPStaticAttr(0,&b));}}
        }
        if(t-last_ae_report>=5){
            last_ae_report=t;ISP_EXP_INFO_S exp{};int e=CVI_ISP_QueryExposureInfo(0,&exp);
            printf("RECORD80_AE_INFO elapsed_s=%.2f rc=0x%x exp_us=%u again=%u dgain=%u isp_gain=%u luma=%u\n",t-start,e,exp.u32ExpTime,exp.u32AGain,exp.u32DGain,exp.u32ISPDGain,exp.u8AveLum);
        }
        if(!blc_check_done && !strcmp(blc_mode,"manual") && t-start>10){
            blc_check_done=true;ISP_INNER_STATE_INFO_S inner{};
            int be=CVI_ISP_QueryInnerStateInfo(0,&inner);
            bool match=!be && inner.blcOffsetR==blc_r && inner.blcOffsetGr==blc_gr &&
                inner.blcOffsetGb==blc_gb && inner.blcOffsetB==blc_b;
            printf("RECORD80_BLC_VERIFY elapsed_s=%.2f rc=0x%x offsets=%u,%u,%u,%u match=%d\n",t-start,be,inner.blcOffsetR,inner.blcOffsetGr,inner.blcOffsetGb,inner.blcOffsetB,match);
            if(!match){tuning_failed=true;running=0;}
        }
        if(!later_sample_done && t-start>15 && getenv("PREVIEW_DIAG_RAW")){later_sample_done=true;printf("CLOCK36_PROBE_BAYER_AFTER_START\n");bayer_sample(argv[2],"after");}
        if(t-start>16 && save_after_jpeg_request.load()==0){save_after_jpeg_request.store(1);printf("CLOCK36_PROBE_JPEG_AFTER_REQUEST\n");}
        if(!last_sample_done && t-start>55 && getenv("PREVIEW_DIAG_RAW")){last_sample_done=true;printf("CLOCK36_LONG_LATE_BAYER\n");bayer_sample(argv[2],"late");}
        if(t-start>56 && save_after_jpeg_request.load()==2){save_after_jpeg_request.store(3);printf("CLOCK36_LONG_LATE_JPEG_REQUEST\n");}
        if(t-start<4){CVI_VI_ReleaseChnFrame(0,0,&frame);continue;}
        if(!count){first=t;firstpts=frame.stVFrame.u64PTS;printf("VI geometry=%ux%u stride=%u,%u format=%d compress=%d video=%d lengths=%u,%u,%u\n",frame.stVFrame.u32Width,frame.stVFrame.u32Height,frame.stVFrame.u32Stride[0],frame.stVFrame.u32Stride[1],frame.stVFrame.enPixelFormat,frame.stVFrame.enCompressMode,frame.stVFrame.enVideoFormat,frame.stVFrame.u32Length[0],frame.stVFrame.u32Length[1],frame.stVFrame.u32Length[2]);}
        else if(frame.stVFrame.u64PTS<=lastpts)++dups;
        last=t;lastpts=frame.stVFrame.u64PTS;++count;
        if(model_path && *model_path){
            if(!npu.prepare(frame))++inference_errors;
        }
        {
            std::lock_guard<std::mutex> guard(input_mutex);
            if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);++preview_replaced;}
            pending=frame;has_pending=true;
        }
        if(t-report>=5 && count>1){
            unsigned long enc=encoded.load(),sent=network_sent.load(),bytes=network_bytes.load();
            printf("capture_frames=%lu host_fps=%.4f pts_fps=%.4f duplicate_pts=%lu timeouts=%lu encoded=%lu infer=%lu infer_errors=%lu infer_avg_ms=%.3f encode_errors=%lu encode_fps=%.3f sent_fps=%.3f jpeg_mbit_s=%.3f preview_replaced=%lu\n",count,(count-1)/(last-first),lastpts>firstpts?(count-1)*1e6/(lastpts-firstpts):0,dups,timeouts,enc,inference_done.load(),inference_errors.load(),inference_done?double(inference_ms.load())/inference_done.load():0.,errors.load(),(enc-last_encoded)/(t-report),(sent-last_sent)/(t-report),(bytes-last_bytes)*8e-6/(t-report),preview_replaced.load());
            double wfps=(count-last_frame_count)/(t-report);double wpts=(last_window_pts&&lastpts>last_window_pts)?(count-last_frame_count)*1000000.0/(lastpts-last_window_pts):0;printf("CLOCK36_WINDOW elapsed_s=%.2f frames=%lu host_fps=%.4f pts_fps=%.4f\n",t-start,count-last_frame_count,wfps,wpts);last_frame_count=count;last_window_pts=lastpts;last_encoded=enc;last_sent=sent;last_bytes=bytes;report=t;
        }
    }
    encoder_thread.join();
    if(infer_thread.joinable())infer_thread.join();
    recorder.stop();
    {std::lock_guard<std::mutex> guard(input_mutex);if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);has_pending=false;}}
    server_thread.join();
    control_thread.join();
    if(created){CVI_VENC_StopRecvFrame(0);CVI_VENC_DestroyChn(0);}
    SAMPLE_COMM_VI_DestroyIsp(&cfg);SAMPLE_COMM_VI_DestroyVi(&cfg);SAMPLE_COMM_SYS_Exit();
    printf("stopped frames=%lu encoded=%lu infer=%lu infer_errors=%lu infer_avg_ms=%.3f errors=%lu tuning_failed=%d\n",count,encoded.load(),inference_done.load(),inference_errors.load(),inference_done?double(inference_ms.load())/inference_done.load():0.,errors.load(),tuning_failed);return rc||errors||tuning_failed?1:0;
}
