#ifndef __ADC_DMA_H
#define __ADC_DMA_H

#include "ch32v30x.h"

/**
  * @brief  初始化多通道 ADC+DMA 连续采样
  * @param  channels  通道号数组（ADC_Channel_0 ~ ADC_Channel_15）
  * @param  num       通道数量（1~16）
  * @param  buf       DMA 循环缓冲区（调用者提供，大小 >= num * 8）
  * @param  buf_size  缓冲区大小（uint16_t 为单位）
  * @note   内部自动校准 ADC，使能连续扫描 + DMA 循环模式
  *         调用 ADC_DMA_Start() 启动转换
  *         仅支持外部通道 CH0~15。CH16(温度)/CH17(Vref) 与外部 DMA 扫描互斥
  *
  *         通道引脚映射：
  *         CH0~7:  PA0~PA7
  *         CH8~9:  PB0~PB1
  *         CH10~15: PC0~PC5
  */
void ADC_DMA_Init(uint8_t channels[], uint8_t num, uint16_t *buf, uint16_t buf_size);

/**
  * @brief  启动 ADC DMA 连续采样
  */
void ADC_DMA_Start(void);

/**
  * @brief  读取指定通道的最新 ADC 值
  * @param  ch_index 通道索引（对应 Init 时 channels[] 的下标 0~num-1）
  * @retval 12 位 ADC 值（0~4095），含校准补偿
  */
uint16_t ADC_DMA_Read(uint8_t ch_index);

#endif
