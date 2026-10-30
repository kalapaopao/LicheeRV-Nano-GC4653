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
#include <condition_variable>
#include "cvi_vpss.h"
#include <atomic>
#include <unistd.h>
#include "record80.h"
#include <poll.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include "cviruntime.h"
#include "yolo26_postprocess.h"
#include "frame_baked_preview.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "vendor/stb_image_write.h"
#include <chrono>
#include <sstream>
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
static std::mutex baked_jpeg_mutex;
static std::vector<unsigned char> baked_latest;
static unsigned long baked_generation=0;
static std::atomic<unsigned long> baked_encoded(0), baked_errors(0), baked_boxes(0);
static std::atomic<unsigned long long> baked_pts(0);
static bool baked_venc_ready=false;
static std::atomic<unsigned long> baked_swjpeg_us(0),baked_dropped(0);
static std::mutex baked_job_mutex;
static std::vector<uint8_t> baked_job_nv21;
static CVI_U64 baked_job_pts=0;
static size_t baked_job_boxes=0;
static bool baked_job_ready=false;
static std::mutex input_mutex;
static VIDEO_FRAME_INFO_S pending{};
static bool has_pending=false;
static std::atomic<unsigned long> encoded(0),errors(0);
static std::atomic<unsigned long> network_sent(0),network_bytes(0),preview_replaced(0);
static std::atomic<unsigned long> inference_done(0),inference_errors(0),inference_ms(0);
static std::atomic<unsigned long> vpss_frames(0),vpss_send_errors(0),vpss_get_errors(0),vpss_queue_drops(0);
static std::atomic<unsigned long> vpss_total_us(0);
static std::mutex detection_mutex;
static std::vector<YoloBox> current_detections;
static double detections_at=0.0, detection_period_ms=0.0;
static std::atomic<unsigned long> postprocess_total_us(0), postprocess_count(0);
static std::mutex vpss_mutex;
static VIDEO_FRAME_INFO_S vpss_pending{};
static bool vpss_has_pending=false;
static bool vpss_active=false;
static const VPSS_GRP VPSS_AI_GRP=1;
static const VPSS_CHN VPSS_AI_CHN=0;
static bool start_vpss(){
    VPSS_GRP_ATTR_S g{};
    g.u32MaxW=1280;g.u32MaxH=720;g.enPixelFormat=PIXEL_FORMAT_NV21;
    g.stFrameRate.s32SrcFrameRate=-1;g.stFrameRate.s32DstFrameRate=-1;
    int ret=CVI_VPSS_CreateGrp(VPSS_AI_GRP,&g);
    if(ret){printf("VPSS_CREATE_ERROR=0x%x\n",(unsigned)ret);return false;}
    VPSS_CHN_ATTR_S a{};
    a.u32Width=320;a.u32Height=320;
    a.enVideoFormat=VIDEO_FORMAT_LINEAR;a.enPixelFormat=PIXEL_FORMAT_NV21;
    a.stFrameRate.s32SrcFrameRate=-1;a.stFrameRate.s32DstFrameRate=-1;
    a.u32Depth=3;
    a.stAspectRatio.enMode=ASPECT_RATIO_AUTO;
    a.stAspectRatio.bEnableBgColor=CVI_TRUE;
    a.stAspectRatio.u32BgColor=0x727272;
    ret=CVI_VPSS_SetChnAttr(VPSS_AI_GRP,VPSS_AI_CHN,&a);
    if(!ret)ret=CVI_VPSS_EnableChn(VPSS_AI_GRP,VPSS_AI_CHN);
    if(!ret)ret=CVI_VPSS_StartGrp(VPSS_AI_GRP);
    if(ret){printf("VPSS_INIT_ERROR=0x%x\n",(unsigned)ret);
        CVI_VPSS_DisableChn(VPSS_AI_GRP,VPSS_AI_CHN);
        CVI_VPSS_DestroyGrp(VPSS_AI_GRP);return false;
    }
    printf("VPSS_STARTED grp=1 chn=0 input=1280x720 output=320x320 nv21 letterbox=auto bg=114\n");
    return true;
}
static void stop_vpss(){
    if(!vpss_active)return;
    {std::lock_guard<std::mutex> g(vpss_mutex);if(vpss_has_pending){
      CVI_VPSS_ReleaseChnFrame(VPSS_AI_GRP,VPSS_AI_CHN,&vpss_pending);vpss_has_pending=false;}}
    CVI_VPSS_DisableChn(VPSS_AI_GRP,VPSS_AI_CHN);
    CVI_VPSS_StopGrp(VPSS_AI_GRP);
    CVI_VPSS_DestroyGrp(VPSS_AI_GRP);
    vpss_active=false;
}
static std::atomic<int> save_after_jpeg_request(0);
static MJPEGRecorder recorder("/code/camera/recordings");
class FlyRmNpu {
    CVI_MODEL_HANDLE model_=nullptr; CVI_TENSOR *input_=nullptr,*output_=nullptr;
    int32_t in_n_=0,out_n_=0;
    bool traced_=false;
public:
    bool open(const char* path){
        if(CVI_NN_RegisterModel(path,&model_)!=0)return false;
        if(CVI_NN_GetInputOutputTensors(model_,&input_,&in_n_,&output_,&out_n_)!=0 || in_n_<1 || out_n_<1)return false;
        if(input_[0].shape.dim[2]!=320 || input_[0].shape.dim[3]!=320){
            fprintf(stderr,"NPU_REQUIRES_320X320\n");return false;}
        input_[0].pixel_format=CVI_NN_PIXEL_YUV_NV21;
        for(int k=0;k<3;k++){input_[0].mean[k]=0.f;input_[0].scale[k]=1.f;}
        return true;
    }
    bool run_frame(const VIDEO_FRAME_INFO_S &f,const char* report_dir,std::vector<YoloBox>& detections){
        if(f.stVFrame.u32Width!=320 || f.stVFrame.u32Height!=320)return false;
        uint64_t addr[1]={f.stVFrame.u64PhyAddr[0]};
        if(CVI_NN_SetTensorWithAlignedFrames(input_,addr,1,CVI_NN_PIXEL_YUV_NV21)!=0)return false;
        bool ok=CVI_NN_Forward(model_,input_,in_n_,output_,out_n_)==0;
        if(ok){
            const size_t bytes=CVI_NN_TensorSize(&output_[0]);
            if(bytes != 5u*2100u*sizeof(float)){
                fprintf(stderr,"NPU_POSTPROCESS_UNSUPPORTED_OUTPUT_BYTES=%zu expected=42000\n",bytes);
                ok=false;
            }else{
                const float* raw=reinterpret_cast<const float*>(CVI_NN_TensorPtr(&output_[0]));
                if(!raw)ok=false;
                else{
                    const auto begin=std::chrono::steady_clock::now();
                    detections=yolo26_decode(raw,2100,0.70f,0.45f,40);
                    const auto end=std::chrono::steady_clock::now();
                    postprocess_total_us+=static_cast<unsigned long>(
                        std::chrono::duration_cast<std::chrono::microseconds>(end-begin).count());
                    ++postprocess_count;
                }
            }
        }
        if(ok && !traced_){
            traced_=true;
            char path[512];snprintf(path,sizeof(path),"%s/vpss_first_320.nv21",report_dir);
            FILE *fp=fopen(path,"wb");
            if(fp){
                const auto &v=f.stVFrame;
                for(int plane=0;plane<2;plane++){
                    unsigned rows=plane?v.u32Height/2:v.u32Height;
                    size_t len=v.u32Length[plane];
                    void *p=CVI_SYS_MmapCache(v.u64PhyAddr[plane],len);
                    if(p){
                        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[plane],p,len);
                        for(unsigned y=0;y<rows;y++)
                            fwrite((unsigned char*)p+y*v.u32Stride[plane],1,v.u32Width,fp);
                        CVI_SYS_Munmap(p,len);
                    }
                }
                fclose(fp);
            }
            snprintf(path,sizeof(path),"%s/npu_first_output.bin",report_dir);
            FILE *op=fopen(path,"wb");
            if(op){
                void *tensor_data=CVI_NN_TensorPtr(&output_[0]);
                size_t n=CVI_NN_TensorSize(&output_[0]);
                if(tensor_data && n>0 && n<10000000){fwrite(tensor_data,1,n,op);}
                fclose(op);
                printf("NPU_TRACE_OUTPUT_BYTES=%zu type=%d shape=%d,%d,%d\n",
                  n,(int)output_[0].fmt,output_[0].shape.dim[0],
                  output_[0].shape.dim[1],output_[0].shape.dim[2]);
            }
        }
        return ok;
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
        bool baked_snapshot=strstr(request,"GET /detect.jpg ")==request;
        bool baked_stream=strstr(request,"GET /detect.mjpg ")==request;
        if(!snapshot && !stream && !baked_snapshot && !baked_stream){
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
#status{color:#9de6d5}#visual{position:relative;width:100%;overflow:hidden;border-radius:8px}
#view{display:block;width:100%;height:auto;background:black}
#boxes{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
#detection{color:#64ecd2;font-variant-numeric:tabular-nums}
small{color:#a6bdcf;display:block;line-height:1.8}
</style><main><h2>GC4653 · 1280×720 · 80FPS 采集 / 40FPS Q85 录像</h2>
<div class="toolbar"><button id="start" onclick="cmd('start')" disabled>● 开始录像</button>
<button id="stop" class="stop" onclick="cmd('stop')" disabled>■ 停止录像</button>
<button id="reconnect" onclick="location.reload()" hidden>重新连接</button>
<span id="status">正在连接录像控制服务…</span></div>
<div class="toolbar"><button onclick="setMode(true)">带框识别（320×320）</button>
<button onclick="setMode(false)">原始预览（1280×720）</button></div>
<div id="visual"><img id="view" src="/detect.mjpg"></div>
<p id="detection">YOLO置信度70% | 检测结果连接中…</p><p id="detail"></p>
<small>录像格式 MJPEG AVI，记录每2帧中的1帧（40FPS），原始取流维持80FPS，无二次 JPEG 编码。录像在板端 /code/camera/recordings，每段最多60秒。视频 FPS 以实际文件解码检测为准。网页显示速率不等于摄像头采集速率。</small>
<script>
const api='http://'+location.hostname+':8082';
let disconnected=false,pollTimer=null,refreshBusy=false,detectionBusy=false;
const requests=new Set();
function setMode(detect){document.getElementById('view').src=detect?'/detect.mjpg':'/live.mjpg';}
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
// Boxes are decoded on the board; the canvas follows the camera's original 1280x720 image.
// NPU ~31FPS and MJPEG ~80FPS are asynchronous; boxes are latest-result overlays,
// not pixel-perfect same-frame snapshots.
async function updateDetections(){
  if(disconnected||detectionBusy)return; detectionBusy=true;
  try{
    const d=await request('/detections',{cache:'no-store'});
    document.getElementById('detection').textContent='同帧板端叠框 | '
      +(d.fps||0).toFixed(1)+' 检测FPS | '
      +(d.post_ms||0).toFixed(2)+'ms 后处理 | '
      +(d.boxes||[]).length+' 个目标 | 带框JPEG '+(d.baked_frames||0)+' 帧';
  }catch(e){document.getElementById('detection').textContent='检测结果不可用：'+e.message;}
  finally{detectionBusy=false;}
}
setInterval(updateDetections,500);
refresh();updateDetections();
</script></main></html>)PAGE";
            sendall(fd,page,sizeof(page)-1);close(fd);continue;
        }
        unsigned long seen=0;
        if(stream || baked_stream){const char hdr[]="HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\nCache-Control: no-store, no-cache\r\nPragma: no-cache\r\nConnection: close\r\n\r\n";if(!sendall(fd,hdr,sizeof(hdr)-1)){close(fd);continue;}}
        while(running){
            std::vector<unsigned char> jpg;
            if(baked_snapshot || baked_stream) {
                std::lock_guard<std::mutex> guard(baked_jpeg_mutex);
                if(baked_generation!=seen){seen=baked_generation;jpg=baked_latest;}
            }else{
                std::lock_guard<std::mutex> guard(jpeg_mutex);
                if(generation!=seen){seen=generation;jpg=latest;}
            }
            if(jpg.empty()){usleep(2000);continue;}
            char hdr[256];
            int count=snprintf(hdr,sizeof(hdr),(snapshot || baked_snapshot)?"HTTP/1.0 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\nCache-Control: no-store\r\n\r\n":"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",jpg.size());
            if(!sendall(fd,hdr,count)||!sendall(fd,jpg.data(),jpg.size()))break;
            ++network_sent;network_bytes+=jpg.size();
            if(snapshot || baked_snapshot)break;
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
        else if(strcmp(method,"GET")==0 && strcmp(route,"/detections")==0){
            std::vector<YoloBox> boxes;
            double age=0,period=0;
            {
                std::lock_guard<std::mutex> lk(detection_mutex);
                boxes=current_detections;
                age=detections_at>0 ? (now()-detections_at)*1000.0 : 1.e9;
                period=detection_period_ms;
            }
            std::ostringstream out;
            out.setf(std::ios::fixed);out.precision(2);
            out<<"{\"model\":\"YOLO26n\",\"class\":\"target\",\"fps\":"
               <<(period>0?1000.0/period:0.0)<<",\"age_ms\":"<<age
               <<",\"post_ms\":"<<(postprocess_count.load()
                  ?postprocess_total_us.load()/double(postprocess_count.load())/1000.0:0.0)
               <<",\"baked_frames\":"<<baked_encoded.load()
               <<",\"baked_errors\":"<<baked_errors.load()
               <<",\"baked_pts\":"<<baked_pts.load()
               <<",\"boxes\":[";
            for(size_t i=0;i<boxes.size();++i){
                if(i)out<<",";
                const YoloBox &b=boxes[i];
                out<<"{\"x1\":"<<b.x1<<",\"y1\":"<<b.y1
                   <<",\"x2\":"<<b.x2<<",\"y2\":"<<b.y2
                   <<",\"score\":"<<b.score<<",\"cls\":"<<b.cls<<"}";
            }
            out<<"]}";
            body=out.str();
        }
        else {status="404 Not Found";body="{\"error\":\"route not found\"}";}        char hdr[512];
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
// Independent, frame-accurate hardware JPEG channel: one VPSS 320x320 frame
// is used by NPU, then annotated in-place, then sent to VENC1 before release.
static void swjpeg_append(void *ctx, void *data, int size) {
    if (!ctx || !data || size<=0) return;
    auto *jpeg=static_cast<std::vector<unsigned char>*>(ctx);
    const auto *p=static_cast<const unsigned char*>(data);
    jpeg->insert(jpeg->end(),p,p+size);
}
// Copy the very same VPSS/NPU frame to software JPEG after writing YOLO boxes.
// This avoids VENC1 rejecting an incompatible video buffer.

// Inference thread: draw into the *same* VPSS frame, then make an owned
// 320x320 NV21 copy, without waiting for JPEG compression.
static bool queue_baked_frame(VIDEO_FRAME_INFO_S &frame,
                              const std::vector<YoloBox> &boxes) {
    if(!baked_nv21_boxes(frame,boxes)){++baked_errors;return false;}
    const auto &v=frame.stVFrame;
    auto *y=static_cast<const uint8_t*>(
        CVI_SYS_MmapCache(v.u64PhyAddr[0],v.u32Length[0]));
    auto *vu=static_cast<const uint8_t*>(
        CVI_SYS_MmapCache(v.u64PhyAddr[1],v.u32Length[1]));
    if(!y || !vu){
        if(y)CVI_SYS_Munmap(const_cast<uint8_t*>(y),v.u32Length[0]);
        if(vu)CVI_SYS_Munmap(const_cast<uint8_t*>(vu),v.u32Length[1]);
        ++baked_errors;return false;
    }
    const bool cache_ok=
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[0],const_cast<uint8_t*>(y),v.u32Length[0])==0 &&
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[1],const_cast<uint8_t*>(vu),v.u32Length[1])==0;
    std::vector<uint8_t> packed;
    if(cache_ok){
        packed.resize(320u*320u*3u/2u);
        for(int row=0;row<320;row++)
            std::memcpy(packed.data()+row*320,y+row*v.u32Stride[0],320);
        for(int row=0;row<160;row++)
            std::memcpy(packed.data()+102400+row*320,vu+row*v.u32Stride[1],320);
    }
    CVI_SYS_Munmap(const_cast<uint8_t*>(vu),v.u32Length[1]);
    CVI_SYS_Munmap(const_cast<uint8_t*>(y),v.u32Length[0]);
    if(!cache_ok){++baked_errors;return false;}
    {
        std::lock_guard<std::mutex> lk(baked_job_mutex);
        if(baked_job_ready)++baked_dropped; // overwrite stale unencoded frame
        baked_job_nv21.swap(packed);
        baked_job_pts=v.u64PTS;
        baked_job_boxes=boxes.size();
        baked_job_ready=true;
    }
    return true;
}
// Only one pending frame is allowed. JPEG worker never blocks NPU/VPSS or
// creates an unbounded queue; all rectangles are already in image pixels.
static void baked_swjpeg_worker(){
    while(true){
        std::vector<uint8_t> packed;
        CVI_U64 pts=0;size_t nboxes=0;
        {
            std::lock_guard<std::mutex> lk(baked_job_mutex);
            if(baked_job_ready){
                packed.swap(baked_job_nv21);
                pts=baked_job_pts;nboxes=baked_job_boxes;
                baked_job_ready=false;
            }
        }
        if(packed.empty()){
            if(!running)break;
            usleep(800);continue;
        }
        std::vector<uint8_t> rgb(320u*320u*3u);
        const uint8_t *y=packed.data();
        const uint8_t *vu=packed.data()+102400;
        auto clamp=[](int x)->uint8_t{return static_cast<uint8_t>(x<0?0:(x>255?255:x));};
        for(int row=0;row<320;row++){
            const uint8_t *yp=y+row*320;
            const uint8_t *cp=vu+(row/2)*320;
            uint8_t *dst=rgb.data()+row*320*3;
            for(int x=0;x<320;x++){
                const int yy=std::max(0,static_cast<int>(yp[x])-16)*298;
                const int vcr=static_cast<int>(cp[x&~1])-128;
                const int ucb=static_cast<int>(cp[(x&~1)+1])-128;
                dst[x*3+0]=clamp((yy+409*vcr+128)>>8);
                dst[x*3+1]=clamp((yy-100*ucb-208*vcr+128)>>8);
                dst[x*3+2]=clamp((yy+516*ucb+128)>>8);
            }
        }
        std::vector<unsigned char> jpg;
        const auto t0=std::chrono::steady_clock::now();
        const int okay=stbi_write_jpg_to_func(swjpeg_append,&jpg,320,320,3,rgb.data(),75);
        const auto dt=std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now()-t0).count();
        baked_swjpeg_us+=static_cast<unsigned long>(dt);
        if(!okay || jpg.size()<4 || jpg[0]!=0xff || jpg[1]!=0xd8){
            ++baked_errors;fprintf(stderr,"BAKED_SWJPEG_FAILURE\n");continue;
        }
        {
            std::lock_guard<std::mutex> lk(baked_jpeg_mutex);
            baked_latest.swap(jpg);
            baked_pts=pts;
            baked_boxes+=nboxes;
            ++baked_generation;
            ++baked_encoded;
        }
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
        printf("FLY_RM_MODEL_READY path=%s input=320x320 format=NV21 preprocess=fused\n",model_path);
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
    if(model_path && *model_path) printf("BAKED_SWJPEG_READY size=320x320 quality=75\n");
    if(model_path && *model_path){
        vpss_active=start_vpss();
        if(!vpss_active){fprintf(stderr,"FATAL_VPSS_INIT_FAILED\n");running=0;}
    }
    printf("YOLO_CONFIDENCE_THRESHOLD=0.70 NMS_IOU=0.45\n");
    recorder.launch();
    if(getenv("RECORD_AUTOSTART") && strcmp(getenv("RECORD_AUTOSTART"),"1")==0)recorder.command(true);
    std::thread server_thread(http_server,server);
    std::thread control_thread(record_control_server,argv[1]);
    std::thread encoder_thread(encoder_worker,argv[2]);
    std::thread baked_thread;
    if(model_path && *model_path)baked_thread=std::thread(baked_swjpeg_worker);
    std::thread infer_thread;
    if(model_path && *model_path){
        infer_thread=std::thread([&](){
            while(running){
                VIDEO_FRAME_INFO_S frame{};bool got=false;
                {std::lock_guard<std::mutex> g(vpss_mutex);
                  if(vpss_has_pending){frame=vpss_pending;vpss_has_pending=false;got=true;}}
                if(!got){usleep(800);continue;}
                std::vector<YoloBox> detections;
                double t0=now();bool ok=npu.run_frame(frame,argv[2],detections);
                if(ok){
                    // Same physical VPSS frame; no asynchronous frame mismatch.
                    queue_baked_frame(frame,detections);
                    ++inference_done;
                    inference_ms+=static_cast<unsigned long>((now()-t0)*1000.0);
                    double ts=now();
                    {
                        std::lock_guard<std::mutex> lk(detection_mutex);
                        if(detections_at>0){
                            const double dt=(ts-detections_at)*1000.;
                            detection_period_ms=detection_period_ms>0 ? detection_period_ms*0.8+dt*0.2 : dt;
                        }
                        detections_at=ts;
                        current_detections.swap(detections);
                    }
                }
                else ++inference_errors;
                CVI_VPSS_ReleaseChnFrame(VPSS_AI_GRP,VPSS_AI_CHN,&frame);
            }
        });
    }
    unsigned vpss_min_gap_ms=0;
    if(!env_u32("CAPTURE_VPSS_MIN_GAP_MS",0,0,50,vpss_min_gap_ms)){
        fprintf(stderr,"Invalid CAPTURE_VPSS_MIN_GAP_MS\n");running=0;
    }
    double last_vpss_feed=0.;
    printf("CAPTURE_FIRST_VPSS mode=pre_encode gap_ms=%u\n",vpss_min_gap_ms);
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
        // Prioritize hardware VPSS before JPEG encoding. VI frame is still owned by capture thread.
        if(vpss_active && running && (!vpss_min_gap_ms || (now()-last_vpss_feed)*1000.>=vpss_min_gap_ms)){
            const double t0=now();
            last_vpss_feed=t0;
            int ve=CVI_VPSS_SendFrame(VPSS_AI_GRP,&frame,5);
            if(ve){++vpss_send_errors;}
            else{
                VIDEO_FRAME_INFO_S processed{};
                ve=CVI_VPSS_GetChnFrame(VPSS_AI_GRP,VPSS_AI_CHN,&processed,20);
                if(ve){++vpss_get_errors;}
                else{
                    if(processed.stVFrame.u32Width!=320 || processed.stVFrame.u32Height!=320)
                        fprintf(stderr,"VPSS_WRONG_SIZE=%ux%u\n",processed.stVFrame.u32Width,processed.stVFrame.u32Height);
                    std::lock_guard<std::mutex> g(vpss_mutex);
                    if(vpss_has_pending){
                        CVI_VPSS_ReleaseChnFrame(VPSS_AI_GRP,VPSS_AI_CHN,&vpss_pending);
                        ++vpss_queue_drops;
                    }
                    vpss_pending=processed;vpss_has_pending=true;++vpss_frames;
                }
            }
            vpss_total_us+=static_cast<unsigned long>((now()-t0)*1000000.);
        }
        {
            std::lock_guard<std::mutex> guard(input_mutex);
            if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);++preview_replaced;}
            pending=frame;has_pending=true;
        }
        if(t-report>=5 && count>1){
            unsigned long enc=encoded.load(),sent=network_sent.load(),bytes=network_bytes.load();
            printf("capture_frames=%lu host_fps=%.4f pts_fps=%.4f duplicate_pts=%lu timeouts=%lu encoded=%lu infer=%lu infer_errors=%lu infer_avg_ms=%.3f encode_errors=%lu encode_fps=%.3f sent_fps=%.3f jpeg_mbit_s=%.3f preview_replaced=%lu\n",count,(count-1)/(last-first),lastpts>firstpts?(count-1)*1e6/(lastpts-firstpts):0,dups,timeouts,enc,inference_done.load(),inference_errors.load(),inference_done?double(inference_ms.load())/inference_done.load():0.,errors.load(),(enc-last_encoded)/(t-report),(sent-last_sent)/(t-report),(bytes-last_bytes)*8e-6/(t-report),preview_replaced.load());
            printf("VPSS_NPU_STATS vpss_frames=%lu send_errors=%lu get_errors=%lu queue_drops=%lu preprocess_avg_us=%lu infer_done=%lu infer_errors=%lu\n",
                vpss_frames.load(),vpss_send_errors.load(),vpss_get_errors.load(),vpss_queue_drops.load(),
                vpss_frames? vpss_total_us.load()/vpss_frames.load():0ul,
                inference_done.load(),inference_errors.load());
            double wfps=(count-last_frame_count)/(t-report);double wpts=(last_window_pts&&lastpts>last_window_pts)?(count-last_frame_count)*1000000.0/(lastpts-last_window_pts):0;printf("CLOCK36_WINDOW elapsed_s=%.2f frames=%lu host_fps=%.4f pts_fps=%.4f\n",t-start,count-last_frame_count,wfps,wpts);last_frame_count=count;last_window_pts=lastpts;last_encoded=enc;last_sent=sent;last_bytes=bytes;report=t;
        }
    }
    encoder_thread.join();
    if(infer_thread.joinable())infer_thread.join();
    if(baked_thread.joinable())baked_thread.join();
    stop_vpss();
    recorder.stop();
    {std::lock_guard<std::mutex> guard(input_mutex);if(has_pending){CVI_VI_ReleaseChnFrame(0,0,&pending);has_pending=false;}}
    server_thread.join();
    control_thread.join();
    if(created){CVI_VENC_StopRecvFrame(0);CVI_VENC_DestroyChn(0);}
    SAMPLE_COMM_VI_DestroyIsp(&cfg);SAMPLE_COMM_VI_DestroyVi(&cfg);SAMPLE_COMM_SYS_Exit();
    printf("BAKED_PREVIEW frames=%lu errors=%lu boxes=%lu last_pts=%llu\n",
           baked_encoded.load(),baked_errors.load(),baked_boxes.load(),
           static_cast<unsigned long long>(baked_pts.load()));
    printf("BAKED_QUEUE_DROPS count=%lu\n",baked_dropped.load());
    printf("BAKED_SWJPEG_TIMING avg_us=%.1f\n", baked_encoded.load()?double(baked_swjpeg_us.load())/baked_encoded.load():0.);
    printf("YOLO26_POSTPROCESS frames=%lu avg_us=%.1f\n",postprocess_count.load(),
           postprocess_count.load()?double(postprocess_total_us.load())/postprocess_count.load():0.);
    printf("VPSS_NPU_FINAL frames=%lu queue_drops=%lu send_errors=%lu get_errors=%lu forwards=%lu forward_errors=%lu\n",vpss_frames.load(),vpss_queue_drops.load(),vpss_send_errors.load(),vpss_get_errors.load(),inference_done.load(),inference_errors.load());
    printf("stopped frames=%lu encoded=%lu infer=%lu infer_errors=%lu infer_avg_ms=%.3f errors=%lu tuning_failed=%d\n",count,encoded.load(),inference_done.load(),inference_errors.load(),inference_done?double(inference_ms.load())/inference_done.load():0.,errors.load(),tuning_failed);return rc||errors||tuning_failed?1:0;
}
