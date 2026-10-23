// Original GC4653 80-mode VI path, with a bounded latest-frame preview worker.
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
#include <fcntl.h>
#include <poll.h>
#include <sys/wait.h>
#include <spawn.h>
extern char **environ;
extern "C" {
#include "sample_comm.h"
}
static volatile sig_atomic_t running=1;
static std::mutex frame_mutex;
static std::vector<unsigned char> latest;
static unsigned long generation=0;
static std::atomic<unsigned long> encoded_inputs(0);
static void stop(int){running=0;}
static double now(){timespec t{}; clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static bool thumbnail(const VIDEO_FRAME_INFO_S& f){
    const auto& v=f.stVFrame;
    if(v.u32Width!=1280 || v.u32Height!=720 || v.enPixelFormat!=PIXEL_FORMAT_NV21) return false;
    std::vector<unsigned char> out(320*180*3/2);
    for(int p=0;p<2;p++){
        size_t size=v.u32Stride[p]*(p?360:720);
        void* ptr=CVI_SYS_MmapCache(v.u64PhyAddr[p],size);
        if(!ptr) return false;
        CVI_SYS_IonInvalidateCache(v.u64PhyAddr[p],ptr,size);
        auto src=static_cast<unsigned char*>(ptr);
        for(int y=0;y<(p?90:180);y++){
            auto row=src+y*4*v.u32Stride[p];
            auto dst=out.data()+(p?320*180:0)+y*320;
            if(!p)for(int x=0;x<320;x++)dst[x]=row[x*4];
            else for(int x=0;x<320;x+=2){dst[x]=row[x*4];dst[x+1]=row[x*4+1];}
        }
        CVI_SYS_Munmap(ptr,size);
    }
    std::lock_guard<std::mutex> guard(frame_mutex);
    latest.swap(out); ++generation;
    return true;
}
static void preview(const char* bind){
    char url[128];snprintf(url,sizeof(url),"http://%s:8080/live.mjpg",bind);
    while(running){
        int fd[2];if(pipe(fd)) break;
        posix_spawn_file_actions_t actions;posix_spawn_file_actions_init(&actions);
        posix_spawn_file_actions_adddup2(&actions,fd[0],STDIN_FILENO);
        posix_spawn_file_actions_addclose(&actions,fd[0]);
        posix_spawn_file_actions_addclose(&actions,fd[1]);
        char* args[]={const_cast<char*>("ffmpeg"),const_cast<char*>("-hide_banner"),const_cast<char*>("-loglevel"),const_cast<char*>("error"),
            const_cast<char*>("-f"),const_cast<char*>("rawvideo"),const_cast<char*>("-pix_fmt"),const_cast<char*>("nv21"),
            const_cast<char*>("-s"),const_cast<char*>("320x180"),const_cast<char*>("-r"),const_cast<char*>("15"),
            const_cast<char*>("-i"),const_cast<char*>("pipe:0"),const_cast<char*>("-threads"),const_cast<char*>("1"),
            const_cast<char*>("-c:v"),const_cast<char*>("mjpeg"),const_cast<char*>("-q:v"),const_cast<char*>("6"),
            const_cast<char*>("-flush_packets"),const_cast<char*>("1"),const_cast<char*>("-f"),const_cast<char*>("mpjpeg"),
            const_cast<char*>("-content_type"),const_cast<char*>("multipart/x-mixed-replace;boundary=ffmpeg"),
            const_cast<char*>("-listen"),const_cast<char*>("1"),url,nullptr};
        pid_t pid=0;int rc=posix_spawnp(&pid,"ffmpeg",&actions,nullptr,args,environ);
        posix_spawn_file_actions_destroy(&actions);close(fd[0]);
        if(rc){close(fd[1]);fprintf(stderr,"ffmpeg spawn error=%d\n",rc);running=0;break;}
        fcntl(fd[1],F_SETFL,fcntl(fd[1],F_GETFL)|O_NONBLOCK);
        unsigned long seen=0;bool ok=true;
        while(running && ok){
            std::vector<unsigned char> frame;
            {std::lock_guard<std::mutex> guard(frame_mutex);if(generation!=seen){frame=latest;seen=generation;}}
            if(frame.empty()){usleep(5000);continue;}
            size_t off=0;
            while(running && off<frame.size()){
                pollfd p{fd[1],POLLOUT,0};int ready=poll(&p,1,100);
                if(ready<0) {if(errno==EINTR)continue;ok=false;break;}
                if(!ready)continue;
                if(p.revents&(POLLERR|POLLHUP|POLLNVAL)){ok=false;break;}
                ssize_t n=write(fd[1],frame.data()+off,frame.size()-off);
                if(n>0)off+=n;
                else if(errno!=EAGAIN && errno!=EINTR){ok=false;break;}
            }
            if(off==frame.size()) ++encoded_inputs;
        }
        close(fd[1]);kill(pid,SIGTERM);
        int status=0;bool reaped=false;
        for(int i=0;i<30;i++){if(waitpid(pid,&status,WNOHANG)==pid){reaped=true;break;}usleep(100000);}
        if(!reaped){kill(pid,SIGKILL);waitpid(pid,&status,0);}
        if(running)usleep(200000); // reconnect without touching the sensor
    }
}
int main(int argc,char** argv){
    if(argc!=2){fprintf(stderr,"Usage: %s USB_BIND_IP\n",argv[0]);return 2;}
    signal(SIGINT,stop);signal(SIGTERM,stop);signal(SIGPIPE,SIG_IGN);
    setvbuf(stdout,nullptr,_IOLBF,0);setenv("MAIX_SENSOR_FPS","80",1);
    SAMPLE_INI_CFG_S ini{};SAMPLE_VI_CONFIG_S cfg{};
    if(SAMPLE_COMM_VI_ParseIni(&ini) || ini.enSnsType[0]!=GCORE_GC4653_MIPI_4M_30FPS_10BIT)return 3;
    ini.enSnsType[0]=GCORE_GC4653_MIPI_720P_60FPS_10BIT;
    CVI_VI_SetDevNum(ini.devNum);
    if(SAMPLE_COMM_VI_IniToViCfg(&ini,&cfg))return 3;
    SIZE_S size{1280,720};if(SAMPLE_PLAT_SYS_INIT(size))return 4;
    if(SAMPLE_PLAT_VI_INIT(&cfg)){SAMPLE_COMM_SYS_Exit();return 5;}
    // SDK initialization installs its own signal handlers; restore ours afterwards.
    signal(SIGINT,stop);signal(SIGTERM,stop);signal(SIGPIPE,SIG_IGN);
    VI_CHN_ATTR_S attr{};int rc=CVI_VI_GetChnAttr(0,0,&attr);attr.u32Depth=2;
    if(!rc)rc=CVI_VI_SetChnAttr(0,0,&attr);
    if(rc)running=0;
    std::thread worker(preview,argv[1]);
    unsigned long count=0,dup=0,timeouts=0;uint64_t prev=0,firstpts=0;
    double start=now(),first=0,last=0,next_preview=0,report=start;
    while(running){
        VIDEO_FRAME_INFO_S f{};
        if(CVI_VI_GetChnFrame(0,0,&f,1000)){if(running)++timeouts;continue;}
        double t=now();uint64_t pts=f.stVFrame.u64PTS;
        if(t-start>=4){
            if(!count){first=t;firstpts=pts;}else if(pts<=prev)++dup;
            last=t;prev=pts;++count;
        }
        if(t>=next_preview){if(!thumbnail(f)){fprintf(stderr,"thumbnail failed\n");rc=6;running=0;}next_preview=t+1.0/15;}
        CVI_VI_ReleaseChnFrame(0,0,&f);
        if(t-report>=5 && count>1){
            printf("capture_frames=%lu host_fps=%.4f pts_fps=%.4f duplicate_pts=%lu timeouts=%lu preview_inputs=%lu\n",count,(count-1)/(last-first),prev>firstpts?(count-1)*1e6/(prev-firstpts):0,dup,timeouts,encoded_inputs.load());report=t;
        }
    }
    worker.join();
    SAMPLE_COMM_VI_DestroyIsp(&cfg);SAMPLE_COMM_VI_DestroyVi(&cfg);SAMPLE_COMM_SYS_Exit();
    printf("stopped frames=%lu duplicate_pts=%lu timeouts=%lu\n",count,dup,timeouts);
    return rc?1:0;
}
