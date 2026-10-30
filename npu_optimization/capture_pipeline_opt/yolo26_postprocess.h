#pragma once
// YOLO26 one-to-many, single class, output FP32 [1,5,2100] in CHW order.
// Coordinates are XYWH in 320x320 letterbox space; raw camera is 1280x720.
#include <vector>
#include <algorithm>
#include <cmath>
#include <cstddef>

struct YoloBox {
    float x1, y1, x2, y2, score;
    int cls;
};

static inline float yolo_clamp(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static inline float yolo_iou(const YoloBox &a, const YoloBox &b) {
    const float w = std::max(0.f, std::min(a.x2, b.x2) - std::max(a.x1, b.x1));
    const float h = std::max(0.f, std::min(a.y2, b.y2) - std::max(a.y1, b.y1));
    const float area_a = (a.x2 - a.x1) * (a.y2 - a.y1);
    const float area_b = (b.x2 - b.x1) * (b.y2 - b.y1);
    const float inter = w * h;
    return inter / (area_a + area_b - inter + 1e-6f);
}

// The output is [xc0..xcN, yc0..ycN, w0..wN, h0..hN, conf0..confN].
// One-to-many export: apply class score threshold followed by class-aware NMS.
// Single class only; never run this routine on the old end2end [1,300,6] model.
static inline std::vector<YoloBox> yolo26_decode(
        const float* data, size_t candidates=2100,
        float confidence=0.25f, float nms_iou=0.45f, size_t max_boxes=40) {
    std::vector<YoloBox> proposals;
    if (!data || candidates == 0 || candidates > 10000) return proposals;
    proposals.reserve(128);
    const float scale = 4.f;  // 1280 / 320, preserving aspect ratio
    const float pad_y = 70.f; // 320 - 720*0.25, then /2
    for (size_t i=0;i<candidates;i++) {
        const float score=data[4*candidates+i];
        if (!std::isfinite(score) || score<confidence || score>1.f) continue;
        const float cx=data[i],cy=data[candidates+i];
        const float w=data[2*candidates+i],h=data[3*candidates+i];
        if (!std::isfinite(cx) || !std::isfinite(cy) ||
            !std::isfinite(w) || !std::isfinite(h) || w<=0 || h<=0) continue;
        YoloBox b{};
        b.x1=yolo_clamp((cx-w*0.5f)*scale,0.f,1280.f);
        b.x2=yolo_clamp((cx+w*0.5f)*scale,0.f,1280.f);
        b.y1=yolo_clamp((cy-h*0.5f-pad_y)*scale,0.f,720.f);
        b.y2=yolo_clamp((cy+h*0.5f-pad_y)*scale,0.f,720.f);
        b.score=score;b.cls=0;
        if (b.x2<=b.x1 || b.y2<=b.y1) continue;
        proposals.push_back(b);
    }
    std::sort(proposals.begin(),proposals.end(),
              [](const YoloBox& a,const YoloBox& b){return a.score>b.score;});
    std::vector<YoloBox> result;
    for (const auto& candidate: proposals) {
        bool duplicate=false;
        for (const auto& selected: result) {
            if (candidate.cls==selected.cls && yolo_iou(candidate,selected)>nms_iou) {
                duplicate=true;break;
            }
        }
        if(!duplicate) result.push_back(candidate);
        if(result.size()>=max_boxes) break;
    }
    return result;
}