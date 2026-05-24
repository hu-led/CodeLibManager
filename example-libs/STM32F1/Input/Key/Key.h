#ifndef __KEY_H
#define __KEY_H
#define KeyGPIO GPIOB

#define KeyNum 1//挂载的按键数
#define Key1Pin GPIO_Pin_1
#define Key1 0

#define KEY_PRESSED 1//按键按下
#define KEY_UNPRESSED 0//按键松开

#define KEY_HOLD				0x01//按键已按下
#define KEY_DOWN				0x02//按键按下瞬间
#define KEY_UP					0x04//按键抬起瞬间
#define KEY_SINGLE				0x08//按键单击
#define KEY_DOUBLE				0x10//按键双击
#define KEY_LONG				0x20//按键长按
#define KEY_REPEAT				0x40//按键长按重复

void key_init(void);
uint8_t Key_GetState(uint8_t key);
uint8_t Key_Check(uint8_t key,uint8_t flag);
void Key_Tick(void);


#endif
