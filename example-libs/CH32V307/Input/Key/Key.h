#ifndef __KEY_H
#define __KEY_H

#include "ch32v30x.h"

/* ── 每个按键的硬件描述 ── */
typedef struct {
    GPIO_TypeDef *port;
    uint16_t      pin;
} KeyConfig_t;

/* ── 按键数量（在 Key.c 的 KeyCfg[] 中填写对应引脚）── */
#define KeyNum 5

/* ── 电平 ── */
#define KEY_PRESSED   1
#define KEY_UNPRESSED 0

/* ── 事件标志位 ── */
#define KEY_HOLD    0x01
#define KEY_DOWN    0x02
#define KEY_UP      0x04
#define KEY_SINGLE  0x08
#define KEY_DOUBLE  0x10
#define KEY_LONG    0x20
#define KEY_REPEAT  0x40

/* ── API ── */
void     key_init(void);
uint8_t  Key_GetState(uint8_t key);
uint8_t  Key_Check(uint8_t key, uint8_t flag);
void     Key_Tick(void);

#endif
