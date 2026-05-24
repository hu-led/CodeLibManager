#include "debug.h"

/**
  * @brief  初始化 TIM2 为 1ms 节拍发生器
  * @note   系统时钟 72MHz，PSC=71/ARR=999，TIM2 定时器频率 1MHz，更新周期 1ms。
  *         更新中断已使能，需在主程序中定义 TIM2_IRQHandler 并添加
  *         __attribute__((interrupt("WCH-Interrupt-fast")))。
  */
void Timer_Init(void)
{
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2, ENABLE);

	TIM_InternalClockConfig(TIM2);

	TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStructure;
	TIM_TimeBaseInitStructure.TIM_ClockDivision = TIM_CKD_DIV1;
	TIM_TimeBaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
	TIM_TimeBaseInitStructure.TIM_Period = 1000 - 1;
	TIM_TimeBaseInitStructure.TIM_Prescaler = 72 - 1;
	TIM_TimeBaseInitStructure.TIM_RepetitionCounter = 0;
	TIM_TimeBaseInit(TIM2, &TIM_TimeBaseInitStructure);

	TIM_ClearFlag(TIM2, TIM_FLAG_Update);
	TIM_ITConfig(TIM2, TIM_IT_Update, ENABLE);

	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);

	NVIC_InitTypeDef NVIC_InitStructure;
	NVIC_InitStructure.NVIC_IRQChannel = TIM2_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 2;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;
	NVIC_Init(&NVIC_InitStructure);

	TIM_Cmd(TIM2, ENABLE);
}

/*
void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")))
{
    if (TIM_GetITStatus(TIM2, TIM_IT_Update) == SET)
    {
        // 在此处添加 1ms 定时任务代码

        TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
    }
}
*/