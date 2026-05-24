#ifndef __USART_H
#define __USART_H

#include "ch32v30x.h"
#include <stdarg.h>

/* ── 硬件配置 ── */
#define USART_INST  USART1   /* USART1 / USART2 / USART3 */
#define USART_BAUD  115200

/* ── 接收缓冲区 ── */
#define USART_RX_BUF_SIZE  128

extern char          USART_RxPacket[];
extern volatile int  USART_RxOver;

/* ── TX API ── */
void USART_Host_Init(void);
void USART_SendByte(uint8_t byte);
void USART_SendArray(uint8_t *arr, uint16_t len);
void USART_SendString(char *str);
void USART_SendNumber(uint32_t num, uint8_t len);
void USART_Printf(char *format, ...);

/* ── RX（用户从 USARTx_IRQHandler 中调用）── */
void USART_RxHandler(uint8_t byte);

#endif
