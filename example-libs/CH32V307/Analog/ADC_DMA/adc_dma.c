#include "adc_dma.h"

static uint16_t *dma_buf;
static uint16_t  buf_size;
static uint8_t   num_channels;
static s16       cal_val = 0;

/**
  * @brief  初始化 ADC + DMA 多通道连续采样
  * @param  channels 通道号数组
  * @param  num      通道数量
  * @param  buf      DMA 缓冲区（外部提供）
  * @param  size     缓冲区大小
  */
void ADC_DMA_Init(uint8_t channels[], uint8_t num, uint16_t *buf, uint16_t size)
{
    GPIO_InitTypeDef  gpio = {0};
    ADC_InitTypeDef   adc  = {0};
    DMA_InitTypeDef   dma  = {0};
    uint8_t i;
    uint32_t rcc_gpio = 0;

    dma_buf      = buf;
    buf_size     = size;
    num_channels = num;

    /* ── 根据通道列表决定需要使能的 GPIO 时钟 ── */
    for (i = 0; i < num; i++) {
        if (channels[i] <= 7)
            rcc_gpio |= RCC_APB2Periph_GPIOA;
        else if (channels[i] <= 9)
            rcc_gpio |= RCC_APB2Periph_GPIOB;
        else if (channels[i] <= 15)
            rcc_gpio |= RCC_APB2Periph_GPIOC;
    }

    /* ── 时钟 ── */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_ADC1 | rcc_gpio, ENABLE);
    RCC_ADCCLKConfig(RCC_PCLK2_Div8);

    /* ── GPIO 模拟输入 ── */
    gpio.GPIO_Mode = GPIO_Mode_AIN;
    for (i = 0; i < num; i++) {
        uint8_t ch = channels[i];
        if (ch <= 7) {
            gpio.GPIO_Pin = (uint16_t)(1 << ch);
            GPIO_Init(GPIOA, &gpio);
        } else if (ch <= 9) {
            gpio.GPIO_Pin = (uint16_t)(1 << (ch - 8));
            GPIO_Init(GPIOB, &gpio);
        } else if (ch <= 15) {
            gpio.GPIO_Pin = (uint16_t)(1 << (ch - 10));
            GPIO_Init(GPIOC, &gpio);
        }
    }

    /* ── ADC 配置 ── */
    ADC_DeInit(ADC1);
    adc.ADC_Mode              = ADC_Mode_Independent;
    adc.ADC_ScanConvMode      = (num > 1) ? ENABLE : DISABLE;
    adc.ADC_ContinuousConvMode = ENABLE;
    adc.ADC_ExternalTrigConv  = ADC_ExternalTrigConv_None;
    adc.ADC_DataAlign         = ADC_DataAlign_Right;
    adc.ADC_NbrOfChannel      = num;
    ADC_Init(ADC1, &adc);

    /* ── 配置通道顺序 ── */
    for (i = 0; i < num; i++) {
        ADC_RegularChannelConfig(ADC1, channels[i], i + 1, ADC_SampleTime_239Cycles5);
    }

    /* ── DMA 循环模式 ── */
    RCC_AHBPeriphClockCmd(RCC_AHBPeriph_DMA1, ENABLE);
    DMA_DeInit(DMA1_Channel1);
    dma.DMA_PeripheralBaseAddr = (uint32_t)(&ADC1->RDATAR);
    dma.DMA_MemoryBaseAddr     = (uint32_t)buf;
    dma.DMA_DIR                = DMA_DIR_PeripheralSRC;
    dma.DMA_BufferSize         = size;
    dma.DMA_PeripheralInc      = DMA_PeripheralInc_Disable;
    dma.DMA_MemoryInc          = DMA_MemoryInc_Enable;
    dma.DMA_PeripheralDataSize = DMA_PeripheralDataSize_HalfWord;
    dma.DMA_MemoryDataSize     = DMA_MemoryDataSize_HalfWord;
    dma.DMA_Mode               = DMA_Mode_Circular;
    dma.DMA_Priority           = DMA_Priority_VeryHigh;
    dma.DMA_M2M                = DMA_M2M_Disable;
    DMA_Init(DMA1_Channel1, &dma);

    ADC_DMACmd(ADC1, ENABLE);
    ADC_Cmd(ADC1, ENABLE);

    /* ── 校准（必须在 ADC_Cmd 之后）── */
    ADC_BufferCmd(ADC1, DISABLE);
    ADC_ResetCalibration(ADC1);
    while (ADC_GetResetCalibrationStatus(ADC1));
    ADC_StartCalibration(ADC1);
    while (ADC_GetCalibrationStatus(ADC1));
    cal_val = Get_CalibrationValue(ADC1);
}

/**
  * @brief  启动 ADC DMA 连续采样
  */
void ADC_DMA_Start(void)
{
    DMA_Cmd(DMA1_Channel1, ENABLE);
    ADC_SoftwareStartConvCmd(ADC1, ENABLE);
}

/**
  * @brief  读取指定通道的最新 ADC 值（含校准补偿）
  * @param  ch_index 通道索引（0 ~ num_channels-1）
  * @retval 校准后的 ADC 值（0~4095）
  */
uint16_t ADC_DMA_Read(uint8_t ch_index)
{
    s32 val;

    if (ch_index >= num_channels) return 0;

    val = (s32)dma_buf[ch_index] + cal_val;
    if (val < 0)     return 0;
    if (val > 4095)  return 4095;
    return (uint16_t)val;
}
