#include "../yolo26_postprocess.h"
#include <cassert>
#include <cstdio>
#include <vector>
int main(){
    const size_t n=2100;
    std::vector<float> o(n*5,0.f);
    // 320x320: center x=160,y=160; 40x40 -> original [560,280,720,440].
    o[0]=160;o[n]=160;o[2*n]=40;o[3*n]=40;o[4*n]=0.90f;
    // Overlapping duplicate, lower confidence, must be suppressed.
    o[1]=161;o[n+1]=160;o[2*n+1]=40;o[3*n+1]=40;o[4*n+1]=0.8f;
    // A second independent positive box.
    o[2]=260;o[n+2]=170;o[2*n+2]=20;o[3*n+2]=20;o[4*n+2]=0.7f;
    // Low confidence must be filtered.
    o[3]=60;o[n+3]=100;o[2*n+3]=20;o[3*n+3]=20;o[4*n+3]=0.1f;
    const auto det=yolo26_decode(o.data(),n);
    assert(det.size()==2);
    assert(det[0].x1==560 && det[0].x2==720);
    assert(det[0].y1==280 && det[0].y2==440);
    assert(det[0].score>det[1].score);
    printf("YOLO26_POSTPROCESS_TEST_OK boxes=%zu first=(%.0f %.0f %.0f %.0f)\n",
           det.size(),det[0].x1,det[0].y1,det[0].x2,det[0].y2);
    return 0;
}