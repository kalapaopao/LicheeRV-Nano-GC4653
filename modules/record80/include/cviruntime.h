#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef enum { CVI_FMT_FP32=0, CVI_FMT_INT8=6, CVI_FMT_UINT8=7 } CVI_FMT;
typedef enum { CVI_NN_PIXEL_YUV_NV12=11, CVI_NN_PIXEL_YUV_NV21=12, CVI_NN_PIXEL_YUV_420_PLANAR=13 } CVI_NN_PIXEL_FORMAT_E;
typedef enum { OPTION_OUTPUT_ALL_TENSORS=4, OPTION_PROGRAM_INDEX=9 } CVI_CONFIG_OPTION;
typedef struct { int32_t dim[6]; size_t dim_size; } CVI_SHAPE;
typedef struct {
  char *name; CVI_SHAPE shape; CVI_FMT fmt; size_t count; size_t mem_size;
  uint8_t *sys_mem; uint64_t paddr; int mem_type; float qscale; int zero_point;
  CVI_NN_PIXEL_FORMAT_E pixel_format; bool aligned; float mean[3]; float scale[3];
  void *owner; char reserved[32];
} CVI_TENSOR;
typedef void *CVI_MODEL_HANDLE; typedef int CVI_RC;
CVI_RC CVI_NN_RegisterModel(const char*, CVI_MODEL_HANDLE*);
CVI_RC CVI_NN_GetInputOutputTensors(CVI_MODEL_HANDLE,CVI_TENSOR**,int32_t*,CVI_TENSOR**,int32_t*);
CVI_RC CVI_NN_SetTensorWithAlignedFrames(CVI_TENSOR*,uint64_t[],int32_t,CVI_NN_PIXEL_FORMAT_E);
CVI_RC CVI_NN_Forward(CVI_MODEL_HANDLE,CVI_TENSOR[],int32_t,CVI_TENSOR[],int32_t);
CVI_RC CVI_NN_CleanupModel(CVI_MODEL_HANDLE);
#ifdef __cplusplus
}
#endif
