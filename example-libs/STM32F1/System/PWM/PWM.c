#include "stm32f10x.h"
const int ARR =100-1;//自动重装值ARR
const int PSC =720-1;//预分频值PSC


/** 
  * @brief  PWM初始化
  * @param  PWM_Percent 占空比（0.0-1.0）
  */
void PWM_Init(double PWM_Percent)
{
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2,ENABLE);

    /*配置时钟源*/
    TIM_InternalClockConfig(TIM2);//设置时钟源为内部时钟

    /*配置时基单元*/
    TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStruct;
    TIM_TimeBaseInitStruct.TIM_ClockDivision=TIM_CKD_DIV1;//时钟分频，用于外部时钟输入的滤波，此处无用
    TIM_TimeBaseInitStruct.TIM_CounterMode=TIM_CounterMode_Up;//向上计数模式
    TIM_TimeBaseInitStruct.TIM_Period=ARR;//自动重装值ARR
    TIM_TimeBaseInitStruct.TIM_Prescaler=PSC;//预分频值PSC
    TIM_TimeBaseInitStruct.TIM_RepetitionCounter=0;//重复定时器，高级定时器功能，此处无用
    TIM_TimeBaseInit(TIM2,&TIM_TimeBaseInitStruct);

    /*配置输出比较单元*/
    TIM_OCInitTypeDef TIM_OCInitStruct;
    TIM_OCStructInit(&TIM_OCInitStruct);//预设为默认值，防止未实际使用的参数未被赋值
    TIM_OCInitStruct.TIM_OCMode=TIM_OCMode_PWM1;//输出比较模式为PWM1
    TIM_OCInitStruct.TIM_OCNPolarity=TIM_OCNPolarity_High;//输出极性为高电平有效
    TIM_OCInitStruct.TIM_OutputState=TIM_OutputState_Enable;//使能输出
    int CCR=PWM_Percent*(ARR+1);
    TIM_OCInitStruct.TIM_Pulse=CCR;//比较值CCR
    TIM_OC1Init(TIM2,&TIM_OCInitStruct);

    /*配置PWM输出端口*/
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA,ENABLE);//使能时钟
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;//输出模式为复用推挽输出
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_0;//默认复用引脚为PA0
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA,&GPIO_InitStructure);

    TIM_Cmd(TIM2,ENABLE);
}
/*
PWM输出频率=CK_PSC/(PSC+1)/(ARR+1)
          =72MHz/720/100
          =1000Hz
PWM占空比=CCR/(ARR+1)
        =50/100
        =50%
PWM分辨率=1/(ARR+1)
        =1%
*/


/** 
  * @brief  调整占空比
  * @param  PWM_Percent 占空比（0.0-1.0）
  */
void PWM_SetPompare1(double PWM_Percent)
{
    int CCR=PWM_Percent*(ARR+1);
    TIM_SetCompare1(TIM2,CCR);
}
