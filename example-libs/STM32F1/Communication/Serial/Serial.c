#include "stm32f10x.h"
#include <stdio.h>
#include <stdarg.h>
#include "Serial.h"

#define Serial_GPIO GPIOA
#define Serial_TX   GPIO_Pin_9
#define Serial_RX   GPIO_Pin_10

char Serial_RxPacket[100];
int SerialState = 0;
int SerialCnt = 0;
int Serial_RxOver = 0;

int ScanCnt = 0;

/**
  * @brief  初始化 USART1（38400-8-N-1，TX=PA9，RX=PA10）
  * @note   开启 RXNE 接收中断，NVIC 分组 2，抢占优先级 1/子优先级 1
  */
void Serial_Init(void)
{
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);

    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_9;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    USART_InitTypeDef USART_InitStructure;
    USART_InitStructure.USART_BaudRate = 38400;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode = USART_Mode_Tx | USART_Mode_Rx;
    USART_InitStructure.USART_Parity = USART_Parity_No;
    USART_InitStructure.USART_StopBits = USART_StopBits_1;
    USART_InitStructure.USART_WordLength = USART_WordLength_8b;
    USART_Init(USART1, &USART_InitStructure);

    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);

    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);

    NVIC_InitTypeDef NVIC_InitStructure;
    NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;
    NVIC_Init(&NVIC_InitStructure);

    USART_Cmd(USART1, ENABLE);
}

/**
  * @brief  串口发送一个字节
  * @param  Byte 要发送的字节
  */
void Serial_SendByte(uint8_t Byte)
{
    USART_SendData(USART1, Byte);
    while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET);
}

/**
  * @brief  串口发送字节数组
  * @param  Array  数组首地址
  * @param  Length 发送长度（字节数）
  */
void Serial_SendArray(uint8_t *Array, uint16_t Length)
{
    uint16_t i;
    for (i = 0; i < Length; i++)
    {
        Serial_SendByte(Array[i]);
    }
}

/**
  * @brief  串口发送字符串（以 '\0' 结尾）
  * @param  String 字符串首地址
  */
void Serial_SendString(char *String)
{
    uint8_t i;
    for (i = 0; String[i] != '\0'; i++)
    {
        Serial_SendByte(String[i]);
    }
}

// 内部辅助：计算 X 的 Y 次方
uint32_t Serial_Pow(uint32_t X, uint32_t Y)
{
    uint32_t Result = 1;
    while (Y--)
    {
        Result *= X;
    }
    return Result;
}

/**
  * @brief  串口发送数字（按指定位宽，高位补空格）
  * @param  Number 要发送的数字（0 - 4294967295）
  * @param  Length 显示位宽（1 - 10）
  */
void Serial_SendNumber(uint32_t Number, uint8_t Length)
{
    uint8_t i;
    for (i = 0; i < Length; i++)
    {
        Serial_SendByte(Number / Serial_Pow(10, Length - i - 1) % 10 + '0');
    }
}

/**
  * @brief  printf 重定向底层函数，将字符通过串口发出
  * @param  ch 要发送的字符
  * @param  f  文件指针（未使用）
  * @retval 返回发送的字符
  */
int fputc(int ch, FILE *f)
{
    Serial_SendByte(ch);
    return ch;
}

// scanf 重定向：从接收缓冲区逐字符读取，遇 '\0' 返回换行
int fgetc(FILE *f)
{
    if (Serial_RxPacket[ScanCnt] == '\0')
    {
        ScanCnt = 0;
        return ((int)'\n');
    }
    ScanCnt++;
    return (int)Serial_RxPacket[ScanCnt - 1];
}

/**
  * @brief  格式化串口输出（类似 printf，无需标准库重定向）
  * @param  format 格式化字符串
  * @param  ...    可变参数列表
  */
void Serial_Printf(char *format, ...)
{
    char String[100];
    va_list arg;
    va_start(arg, format);
    vsprintf(String, format, arg);
    va_end(arg);
    Serial_SendString(String);
}

// USART1 接收中断：数据包以 "\r\n" 结尾，存入 Serial_RxPacket 后置位 Serial_RxOver
void USART1_IRQHandler(void)
{
    if (USART_GetITStatus(USART1, USART_IT_RXNE) == SET)
    {
        uint8_t RxData = USART_ReceiveData(USART1);
        if (RxData == '\r')
        {
            SerialState = 1;
        }
        else if ((RxData == '\n' && SerialState == 1) || (SerialCnt >= 99))
        {
            SerialState = 0;
            Serial_RxPacket[SerialCnt] = '\0';
            SerialCnt = 0;
            Serial_RxOver = 1;
        }
        else
        {
            Serial_RxPacket[SerialCnt] = RxData;
            SerialCnt++;
        }
        USART_ClearITPendingBit(USART1, USART_IT_RXNE);
    }
}
