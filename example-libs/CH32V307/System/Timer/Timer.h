#ifndef __TIMER_H
#define __TIMER_H

void Timer_Init(void);

#endif
/*
使用示例

int main(void)
{
    // 1. 初始化按键 GPIO
    key_init();
    // 2. 配置 TIM2 为 1ms 定时中断
    Timer_Init();
    while (1)
    {
        // 3. 主循环中轮询事件
        if (Key_Check(Key1, KEY_DOWN)) {
            // 按键刚按下时做某事
        }
        if (Key_Check(Key1, KEY_SINGLE)) {
            // 单击触发
        }
        if (Key_Check(Key1, KEY_LONG)) {
            // 长按触发
        }
        if (Key_Check(Key1, KEY_REPEAT)) {
            // 长按重复触发（例如音量+/-连续调节）
        }
        // KEY_HOLD 不清除，持续检测：
        if (Key_Check(Key1, KEY_HOLD)) {
            // 按键正在按住中...
        }
    }
}
*/
