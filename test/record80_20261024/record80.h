#pragma once
// Native AVI muxer for the already-verified 1280x720 JPEG VENC stream.
// No second hardware encoder and no FFmpeg process during recording.
// Every successfully written JPEG becomes exactly one AVI MJPG frame.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <ctime>
#include <deque>
#include <vector>
#include <string>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <chrono>
#include <cstdint>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

class MJPEGRecorder {
public:
    explicit MJPEGRecorder(const std::string& d): dir_(d) {}
    ~MJPEGRecorder(){stop();}
    std::atomic<bool> requested{false}, active{false};
    std::atomic<unsigned long> written{0}, dropped{0}, files{0}, write_errors{0};
    std::atomic<unsigned long long> written_bytes{0};
    std::atomic<double> segment_start{0};
    std::mutex mutex_;
    std::condition_variable cv_;
    std::deque<std::vector<unsigned char>> queue_;
    std::string current_, last_, error_, dir_;
    std::thread writer_;
    std::atomic<bool> closing{false};

    void launch(){writer_=std::thread(&MJPEGRecorder::loop,this);}
    void command(bool on){requested.store(on); cv_.notify_one();}
    void push(const std::vector<unsigned char>& jpg){
        if(!requested.load()||closing.load())return;
        std::lock_guard<std::mutex> lock(mutex_);
        if(queue_.size()>=32){dropped++;return;}
        queue_.push_back(jpg);
        cv_.notify_one();
    }
    void stop(){
        if(!writer_.joinable())return;
        requested=false;
        closing=true;
        cv_.notify_one();
        writer_.join();
    }
    std::string status(){
        std::string name,last,error;
        {std::lock_guard<std::mutex> lock(mutex_);name=current_;last=last_;error=error_;}
        char buf[1400];
        snprintf(buf,sizeof(buf),
          "{\"requested\":%s,\"recording\":%s,\"file\":\"%s\",\"last\":\"%s\","
          "\"written\":%lu,\"dropped\":%lu,\"bytes\":%llu,\"segments\":%lu,"
          "\"write_errors\":%lu,\"elapsed\":%.2f,\"error\":\"%s\"}",
          requested.load()?"true":"false",active.load()?"true":"false",
          name.c_str(),last.c_str(),written.load(),dropped.load(),
          written_bytes.load(),files.load(),write_errors.load(),
          active.load()?now()-segment_start.load():0,error.c_str());
        return buf;
    }
private:
    struct Idx {uint32_t offset, bytes;};
    std::vector<Idx> index_;
    FILE *out_=nullptr;
    std::string tmp_,final_;
    unsigned long seq_=0,at_start_frames_=0,at_start_drops_=0;
    unsigned long long at_start_bytes_=0;
    long riff_len_=0,avih_frames_=0,strh_frames_=0,movi_len_=0;
    static double now(){
        timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);
        return double(t.tv_sec)+double(t.tv_nsec)*1e-9;
    }
    void err(const char* msg){
        {std::lock_guard<std::mutex> lock(mutex_);error_=msg;}
        fprintf(stderr,"RECORD_ERROR %s\n",msg);
    }
    bool space_ok(){
        struct statvfs v{};
        return statvfs(dir_.c_str(),&v)==0 &&
            (unsigned long long)v.f_bavail*v.f_frsize>=150ull*1024*1024;
    }
    static void fcc(FILE* f,const char* code){fwrite(code,1,4,f);}
    static void u16(FILE*f,uint16_t n){uint8_t b[2]={(uint8_t)n,(uint8_t)(n>>8)};fwrite(b,1,2,f);}
    static void u32(FILE*f,uint32_t n){
        uint8_t b[4]={(uint8_t)n,(uint8_t)(n>>8),(uint8_t)(n>>16),(uint8_t)(n>>24)};
        fwrite(b,1,4,f);
    }
    void patch(long offset,uint32_t value){
        long pos=ftell(out_);
        fseek(out_,offset,SEEK_SET);
        u32(out_,value);
        fseek(out_,pos,SEEK_SET);
    }
    bool start(){
        if(dir_!="/code/camera/recordings"){err("Recording path rejected");return false;}
        if(mkdir(dir_.c_str(),0755)&&errno!=EEXIST){err("mkdir failed");return false;}
        if(!space_ok()){err("Not enough free storage");return false;}
        time_t epoch=time(nullptr);tm utc{};gmtime_r(&epoch,&utc);
        char date[24];strftime(date,sizeof(date),"%Y%m%d_%H%M%S",&utc);
        char name[128];
        snprintf(name,sizeof(name),"gc4653_%s_%d_%04lu_720p40.avi",date,(int)getpid(),++seq_);
        tmp_=dir_+"/"+name+".part";
        final_=dir_+"/"+name;
        if(access(tmp_.c_str(),F_OK)==0||access(final_.c_str(),F_OK)==0){
            err("Recording name exists");return false;
        }
        out_=fopen(tmp_.c_str(),"wb+");
        if(!out_){err("Cannot open AVI output");return false;}
        setvbuf(out_,nullptr,_IOFBF,1<<20);
        // RIFF AVI main chunk
        fcc(out_,"RIFF");riff_len_=ftell(out_);u32(out_,0);fcc(out_,"AVI ");
        fcc(out_,"LIST");long hdrl=ftell(out_);u32(out_,0);fcc(out_,"hdrl");
        fcc(out_,"avih");u32(out_,56);
        u32(out_,25000); // stored frames: 40 fps; sensor/preview still 80 fps
        u32(out_,25000000);u32(out_,0);u32(out_,0x10); // has index
        avih_frames_=ftell(out_);u32(out_,0); // dwTotalFrames
        u32(out_,0);u32(out_,1);u32(out_,2*1024*1024);
        u32(out_,1280);u32(out_,720);
        for(int i=0;i<4;i++)u32(out_,0);
        // One MJPG video stream
        fcc(out_,"LIST");long strl=ftell(out_);u32(out_,0);fcc(out_,"strl");
        fcc(out_,"strh");u32(out_,56);
        fcc(out_,"vids");fcc(out_,"MJPG");
        u32(out_,0);u16(out_,0);u16(out_,0);u32(out_,0);
        u32(out_,1);u32(out_,40);u32(out_,0);
        strh_frames_=ftell(out_);u32(out_,0);
        u32(out_,2*1024*1024);u32(out_,0xffffffffu);u32(out_,0);
        u16(out_,0);u16(out_,0);u16(out_,1280);u16(out_,720);
        // BITMAPINFOHEADER
        fcc(out_,"strf");u32(out_,40);
        u32(out_,40);u32(out_,1280);u32(out_,720);
        u16(out_,1);u16(out_,24);fcc(out_,"MJPG");
        u32(out_,1280*720*3);
        u32(out_,0);u32(out_,0);u32(out_,0);u32(out_,0);
        patch(strl,(uint32_t)(ftell(out_)-strl-4));
        patch(hdrl,(uint32_t)(ftell(out_)-hdrl-4));
        fcc(out_,"LIST");movi_len_=ftell(out_);u32(out_,0);fcc(out_,"movi");
        if(ferror(out_)){err("AVI header write failed");fclose(out_);out_=nullptr;return false;}
        index_.clear();
        at_start_frames_=written.load();
        at_start_drops_=dropped.load();
        at_start_bytes_=written_bytes.load();
        segment_start=now();
        {std::lock_guard<std::mutex> lock(mutex_);current_=name;error_.clear();}
        active=true;
        fprintf(stderr,"RECORD_STARTED native_avi=%s\n",tmp_.c_str());
        return true;
    }
    bool put_frame(const std::vector<unsigned char>& jpg){
        if(!out_||jpg.size()<4||jpg.size()>2*1024*1024||
           jpg[0]!=0xff||jpg[1]!=0xd8){err("Invalid JPEG VENC packet");return false;}
        long at=ftell(out_);
        if(at<0)return false;
        fcc(out_,"00dc");u32(out_,(uint32_t)jpg.size());
        if(fwrite(jpg.data(),1,jpg.size(),out_)!=jpg.size())return false;
        if(jpg.size()&1)fputc(0,out_);
        if(ferror(out_))return false;
        // idx1 offsets are relative to the 'movi' fourcc, first chunk=4.
        index_.push_back({(uint32_t)(at-(movi_len_+4)),(uint32_t)jpg.size()});
        ++written;
        written_bytes+=jpg.size();
        return true;
    }
    void finish(){
        if(!active.load())return;
        active=false;
        long end_movi=ftell(out_);
        patch(movi_len_,(uint32_t)(end_movi-movi_len_-4));
        fcc(out_,"idx1");u32(out_,uint32_t(index_.size()*16));
        for(const auto& item:index_){
            fcc(out_,"00dc");u32(out_,0x10);u32(out_,item.offset);u32(out_,item.bytes);
        }
        long end=ftell(out_);
        patch(riff_len_,(uint32_t)(end-8));
        patch(avih_frames_,(uint32_t)index_.size());
        patch(strh_frames_,(uint32_t)index_.size());
        bool ok=!ferror(out_) && fflush(out_)==0;
        if(fclose(out_)!=0)ok=false;
        out_=nullptr;
        unsigned long frames=written.load()-at_start_frames_;
        double elapsed=now()-segment_start.load();
        if(!ok||!frames){err("AVI finalization error or zero frames");return;}
        if(rename(tmp_.c_str(),final_.c_str())!=0){err("AVI rename failed");return;}
        ++files;
        FILE* f=fopen((final_+".json").c_str(),"w");
        if(f){
            fprintf(f,"{\"codec\":\"MJPEG\",\"width\":1280,\"height\":720,\"nominal_fps\":40,\"capture_target_fps\":80,"
             "\"frames\":%lu,\"elapsed_sec\":%.3f,\"fps_by_elapsed\":%.3f,\"jpeg_bytes\":%llu,"
             "\"queue_drops\":%lu,\"write_errors\":%lu}\n",
             frames,elapsed,elapsed?frames/elapsed:0.,
             written_bytes.load()-at_start_bytes_,dropped.load()-at_start_drops_,write_errors.load());
            fclose(f);
        }
        {std::lock_guard<std::mutex> lock(mutex_);last_=current_;current_.clear();}
        fprintf(stderr,"RECORD_FINISHED file=%s frames=%lu elapsed=%.3f record_fps=%.3f queue_drops=%lu\n",
          final_.c_str(),frames,elapsed,elapsed?frames/elapsed:0.,dropped.load()-at_start_drops_);
    }
    void loop(){
        while(true){
            if(requested.load()&&!active.load() && !start())requested=false;
            std::vector<unsigned char> jpg;
            {std::unique_lock<std::mutex> lock(mutex_);
             cv_.wait_for(lock,std::chrono::milliseconds(40),[&]{
                return !queue_.empty()||closing.load()||requested.load()!=active.load();
             });
             if(!queue_.empty()){jpg=std::move(queue_.front());queue_.pop_front();}
            }
            if(!jpg.empty() && active.load() && !put_frame(jpg)){
                ++write_errors;requested=false;
            }
            if(active.load() && (now()-segment_start.load()>60 ||
               written_bytes.load()-at_start_bytes_>=350ull*1024*1024 ||
               !space_ok())){
                finish();
                if(!space_ok()){err("Low storage; recording stopped");requested=false;}
            }
            bool empty;
            {std::lock_guard<std::mutex> lock(mutex_);empty=queue_.empty();}
            if(active.load()&&(!requested.load()||closing.load())&&empty)finish();
            if(closing.load()&&!active.load()&&empty)break;
        }
    }
};
