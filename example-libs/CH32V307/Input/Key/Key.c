#include "ch32v30x.h"
#include "Key.h"

#define KEY_DOUBLE_ENABLE 0
#define KEY_TIME_DOUBLE  300
#define KEY_TIME_LONG   1600
#define KEY_TIME_REPEAT  100

/* ── 硬件配置：每个按键的 GPIO 端口和引脚 ── */
static const KeyConfig_t KeyCfg[KeyNum] = {
    {GPIOE, GPIO_Pin_1},   // [0] 上 PE1
    {GPIOE, GPIO_Pin_2},   // [1] 下 PE2
    {GPIOD, GPIO_Pin_6},   // [2] 左 PD6
    {GPIOE, GPIO_Pin_3},   // [3] 右 PE3
    {GPIOD, GPIO_Pin_13},  // [4] 按下 PD13
};

uint8_t Key_flag[KeyNum + 2];

static void key_enable_port(GPIO_TypeDef *port)
{
         if (port == GPIOA) RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    else if (port == GPIOB) RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB, ENABLE);
    else if (port == GPIOC) RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOC, ENABLE);
    else if (port == GPIOD) RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD, ENABLE);
    else if (port == GPIOE) RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOE, ENABLE);
}

/**
  * @brief  初始化所有按键 GPIO（IPU 上拉输入，低电平按下）
  */
void key_init()
{
    GPIO_InitTypeDef s;
    s.GPIO_Mode  = GPIO_Mode_IPU;
    s.GPIO_Speed = GPIO_Speed_50MHz;

    for (int i = 0; i < KeyNum; i++)
    {
        int seen = 0;
        for (int j = 0; j < i; j++)
            if (KeyCfg[j].port == KeyCfg[i].port) { seen = 1; break; }
        if (seen) continue;
        key_enable_port(KeyCfg[i].port);
    }

    for (int i = 0; i < KeyNum; i++)
    {
        s.GPIO_Pin = KeyCfg[i].pin;
        GPIO_Init(KeyCfg[i].port, &s);
    }
}

/**
  * @brief  读取按键原始状态
  * @param  key 按键索引（0..KeyNum-1）
  * @retval KEY_PRESSED(1) 按下，KEY_UNPRESSED(0) 松开
  */
uint8_t Key_GetState(uint8_t key)
{
    if (key >= KeyNum) return KEY_UNPRESSED;
    if (GPIO_ReadInputDataBit(KeyCfg[key].port, KeyCfg[key].pin) == 0)
        return KEY_PRESSED;
    return KEY_UNPRESSED;
}

/**
  * @brief  检查按键事件标志（除 HOLD 外，检查后自动清除）
  * @param  key  按键索引
  * @param  flag 事件标志位：KEY_DOWN/UP/HOLD/SINGLE/DOUBLE/LONG/REPEAT
  * @retval 1=事件已发生，0=未发生
  */
uint8_t Key_Check(uint8_t key, uint8_t flag)
{
    if (Key_flag[key] & flag)
    {
        if (flag != KEY_HOLD)
            Key_flag[key] &= (~flag);
        return 1;
    }
    return 0;
}

/**
  * @brief  按键状态机时基（每 1ms 调用一次）
  * @note   内部 20ms 消抖。需在 TIM2_IRQHandler 中调用：
  *         void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")))
  *         { if (TIM_GetITStatus(TIM2, TIM_IT_Update) != RESET)
  *           { Key_Tick(); TIM_ClearITPendingBit(TIM2, TIM_IT_Update); } }
  */
void Key_Tick()
{
    static uint8_t  count;
    static uint8_t  CurrState[KeyNum + 2];
    static uint8_t  PrevState[KeyNum + 2];
    static uint8_t  State[KeyNum + 2];
    static uint16_t Time[KeyNum + 2];

    for (int i = 0; i < KeyNum; i++)
        if (Time[i] > 0) Time[i]--;

    count++;
    if (count >= 20)
    {
        count = 0;
        for (int i = 0; i < KeyNum; i++)
        {
            PrevState[i] = CurrState[i];
            CurrState[i] = Key_GetState(i);

            if (CurrState[i] == KEY_PRESSED)
                Key_flag[i] |= KEY_HOLD;
            else
                Key_flag[i] &= (~KEY_HOLD);

            if ((CurrState[i] == KEY_PRESSED) && (PrevState[i] == KEY_UNPRESSED))
                Key_flag[i] |= KEY_DOWN;

            if ((CurrState[i] == KEY_UNPRESSED) && (PrevState[i] == KEY_PRESSED))
                Key_flag[i] |= KEY_UP;

            if (State[i] == 0)
            {
                if (CurrState[i] == KEY_PRESSED)
                    { Time[i] = KEY_TIME_LONG; State[i] = 1; }
            }
            else if (State[i] == 1)
            {
                if (CurrState[i] == KEY_UNPRESSED)
                {
#if KEY_DOUBLE_ENABLE
                    Time[i]  = KEY_TIME_DOUBLE;
                    State[i] = 2;
#else
                    Key_flag[i] |= KEY_SINGLE;
                    State[i] = 0;
#endif
                }
                else if (Time[i] == 0)
                    { Time[i] = KEY_TIME_REPEAT; Key_flag[i] |= KEY_LONG; State[i] = 4; }
            }
#if KEY_DOUBLE_ENABLE
            else if (State[i] == 2)
            {
                if (CurrState[i] == KEY_PRESSED)
                    { Key_flag[i] |= KEY_DOUBLE; State[i] = 3; }
                else if (Time[i] == 0)
                    { Key_flag[i] |= KEY_SINGLE; State[i] = 0; }
            }
            else if (State[i] == 3)
            {
                if (CurrState[i] == KEY_UNPRESSED) State[i] = 0;
            }
#endif
            else if (State[i] == 4)
            {
                if (CurrState[i] == KEY_UNPRESSED)
                    State[i] = 0;
                else if (Time[i] == 0)
                    { Time[i] = KEY_TIME_REPEAT; Key_flag[i] |= KEY_REPEAT; State[i] = 4; }
            }
        }
    }
}
