#include "debug.h"
#define LEDPin GPIO_Pin_11 //LED1
//#define LEDPin GPIO_Pin_12 //LED2

/**
 * @brief LED初始化,默认使用板载LED1,PE11
 */
void LED_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure = {0};

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOE, ENABLE);
    GPIO_InitStructure.GPIO_Pin = LEDPin;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOE, &GPIO_InitStructure);

}

/**
 * @brief 点亮LED
 */
void LED_ON(void)
{
    GPIO_ResetBits(GPIOE, LEDPin);
}

/**
 * @brief 熄灭LED
 */
void LED_OFF(void)
{
    GPIO_SetBits(GPIOE, LEDPin);
}

/**
 * @brief 翻转LED
 */
void LED_Toggle(void)
{
    if (GPIO_ReadOutputDataBit(GPIOE, LEDPin) == 0)
        GPIO_SetBits(GPIOE, LEDPin);
    else
        GPIO_ResetBits(GPIOE, LEDPin);
}