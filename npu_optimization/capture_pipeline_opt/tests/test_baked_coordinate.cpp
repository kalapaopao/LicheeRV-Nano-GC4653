#include "../yolo26_postprocess.h"
#include <cassert>
#include <vector>
int main() {
    // The NPU sees letterbox, with the 720p image occupying y=70..250.
    std::vector<float> output(5*2100,0);
    output[0]=160; output[2100]=160;
    output[4200]=40;output[6300]=40;output[8400]=0.9f;
    auto boxes=yolo26_decode(output.data());
    assert(boxes.size()==1);
    auto b=boxes[0];
    assert(b.x1==560 && b.x2==720 && b.y1==280 && b.y2==440);
    assert(b.x1/4==140 && b.x2/4==180);
    assert(b.y1/4+70==140 && b.y2/4+70==180);
    return 0;
}
