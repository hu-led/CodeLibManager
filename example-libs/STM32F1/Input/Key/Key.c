#include "stm32f10x.h"
#include "Key.h"

#define KEY_DOUBLE_ENABLE 0//双击使能：1=启用，0=失能以加快单击响应（无需窗口等待）
#define KEY_TIME_DOUBLE	300//双击检测窗口 300ms
#define KEY_TIME_LONG 1600//长按检测阈值 1600ms
#define KEY_TIME_REPEAT	100//重复触发间隔 100ms

uint8_t Key_flag[KeyNum+2];

/**
  * @brief  初始化按键 GPIO（PB1，内部上拉，低电平有效）
  */
void key_init()
{
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);

    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_InitStructure.GPIO_Pin = Key1Pin;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(KeyGPIO,&GPIO_InitStructure);
}
/**
  * @brief  读取按键原始状态
  * @param  key 按键编号（Key1=0）
  * @retval KEY_PRESSED(1) 按下，KEY_UNPRESSED(0) 松开
  */
uint8_t Key_GetState(uint8_t key)
{
    if(key==Key1)
    {
        if (GPIO_ReadInputDataBit(KeyGPIO, Key1Pin) == 0)
		{
			return KEY_PRESSED;
		}
    }
    return KEY_UNPRESSED;
}
/**
  * @brief  检查按键事件标志（除 HOLD 外检查后自动清除）
  * @param  key  按键编号
  * @param  flag 事件标志位：KEY_DOWN/UP/HOLD/SINGLE/DOUBLE/LONG/REPEAT
  * @retval 1=事件已发生，0=未发生
  */
uint8_t Key_Check(uint8_t key,uint8_t flag)
{
    if(Key_flag[key]&flag)
    {
        if(flag!=KEY_HOLD)
        {
            Key_flag[key]&=(~flag);
        }
        return 1;
    }
    return 0;
}
/**
  * @brief  按键状态机时基（由 TIM2_IRQHandler 每 1ms 调用）
  * @note   内部消抖 20ms，更新标志位供 Key_Check 读取
  */
void Key_Tick()
{
    static uint8_t count;
	static uint8_t CurrState[KeyNum+2];//上一按键状态
    static uint8_t PrevState[KeyNum+2];//当前按键状态
	static uint8_t State[KeyNum+2];//当前状态机状态
	static uint16_t Time[KeyNum+2];//计时
    for(int i=0;i<KeyNum;i++)
    {
        if(Time[i]>0)
        {
            Time[i]--;
        }
    }
    count++;
    if(count>=20)
    {
        count=0;
        for(int i=0;i<KeyNum;i++)
        {
            PrevState[i]=CurrState[i];
            CurrState[i]=Key_GetState(i);
            if(CurrState[i]==KEY_PRESSED)//当前按键按下
            {
                Key_flag[i]|=KEY_HOLD;
            }
            else 
            {
                Key_flag[i]&=(~KEY_HOLD);
            }
            if((CurrState[i]==KEY_PRESSED)&&(PrevState[i]==KEY_UNPRESSED))//按键按下时刻
			{
				Key_flag[i]|=KEY_DOWN;
			}
			if((CurrState[i]==KEY_UNPRESSED)&&(PrevState[i]==KEY_PRESSED))//按键松开时刻
			{
				Key_flag[i]|=KEY_UP;
			}

            if(State[i]==0)
            {
                if(CurrState[i]==KEY_PRESSED)//0状态时按键按下
                {
                    Time[i]=KEY_TIME_LONG;
                    State[i]=1;
                }
            }
            else if(State[i]==1)
            {
                if(CurrState[i]==KEY_UNPRESSED)//按键松开
                {
#if KEY_DOUBLE_ENABLE
                    Time[i]=KEY_TIME_DOUBLE;
                    State[i]=2;
#else
                    Key_flag[i]|=KEY_SINGLE;
                    State[i]=0;
#endif
                }
                else if(Time[i]==0)//长按按下
                {
                    Time[i]=KEY_TIME_REPEAT;
                    Key_flag[i]|=KEY_LONG;
                    State[i]=4;
                }
            }
#if KEY_DOUBLE_ENABLE
            else if(State[i]==2)
            {
                if(CurrState[i]==KEY_PRESSED)//双击按下
                {
                    Key_flag[i]|=KEY_DOUBLE;
                    State[i]=3;
                }
                else if(Time[i]==0)//单击松开
                {
                    Key_flag[i]|=KEY_SINGLE;
                    State[i]=0;
                }
            }
            else if(State[i]==3)
            {
                if(CurrState[i]==KEY_UNPRESSED)//双击松开
                {
                    State[i]=0;
                }
            }
#endif
            else if(State[i]==4)
            {
                if(CurrState[i]==KEY_UNPRESSED)//长按松开
                {
                    State[i]=0;
                }
                else if(Time[i]==0)//长按重复
                {
                    Time[i]=KEY_TIME_REPEAT;
                    Key_flag[i]|=KEY_REPEAT;
                    State[i]=4;
                }
            }
        }
    }
}
void TIM2_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM2, TIM_IT_Update) == SET)
    {
        Key_Tick();
        TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
    }
}
