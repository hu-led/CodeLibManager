#include "IIC.h"
#include "debug.h"



/**
  * @brief  初始化 I2C2 硬件外设（PB10=SCL, PB11=SDA）
  * @note   多设备共享 I2C 总线时，上电 BUSY 标志可能误置。
  *         本函数在标准初始化前执行 Bus Recovery（GPIO 拨 SCL 9 次）
  *         和 I2C 软件复位（SWRST），确保总线从异常状态恢复。
  * @param  bound    I2C 时钟频率（Hz），常用 200000（200kHz）
  * @param  address  本机 7 位地址（主模式下通常为 0x02）
  */
void IIC_Init( u32 bound , u16 address )
{
	GPIO_InitTypeDef GPIO_InitStructure;
	I2C_InitTypeDef I2C_InitTSturcture;
	u8 i;

	RCC_APB2PeriphClockCmd( RCC_APB2Periph_GPIOB , ENABLE );
	RCC_APB1PeriphClockCmd( RCC_APB1Periph_I2C2, ENABLE );

	/* ── Bus Recovery：GPIO 模式下拨 SCL 9 次，释放被卡住的从设备 ── */
	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init( GPIOB, &GPIO_InitStructure );

	GPIO_SetBits( GPIOB, GPIO_Pin_10 | GPIO_Pin_11 );

	for ( i = 0; i < 9; i++ )
	{
		GPIO_ResetBits( GPIOB, GPIO_Pin_10 );
		Delay_Us( 10 );
		GPIO_SetBits( GPIOB, GPIO_Pin_10 );
		Delay_Us( 10 );
	}

	/* STOP 条件：SCL 高时 SDA 低→高 */
	GPIO_ResetBits( GPIOB, GPIO_Pin_11 );
	Delay_Us( 10 );
	GPIO_SetBits( GPIOB, GPIO_Pin_10 );
	Delay_Us( 10 );
	GPIO_SetBits( GPIOB, GPIO_Pin_11 );

	/* ── I2C 外设软件复位，清除 BUSY 标志 ── */
	I2C_SoftwareResetCmd( I2C2, ENABLE );
	Delay_Ms( 5 );
	I2C_SoftwareResetCmd( I2C2, DISABLE );

	/* ── 正常 AF_OD 配置 ── */
	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_10;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_OD;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init( GPIOB, &GPIO_InitStructure );

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_11;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_OD;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init( GPIOB, &GPIO_InitStructure );

	I2C_InitTSturcture.I2C_ClockSpeed = bound;
	I2C_InitTSturcture.I2C_Mode = I2C_Mode_I2C;
	I2C_InitTSturcture.I2C_DutyCycle = I2C_DutyCycle_16_9;
	I2C_InitTSturcture.I2C_OwnAddress1 = address;
	I2C_InitTSturcture.I2C_Ack = I2C_Ack_Enable;
	I2C_InitTSturcture.I2C_AcknowledgedAddress = I2C_AcknowledgedAddress_7bit;
	I2C_Init( I2C2, &I2C_InitTSturcture );

	I2C_Cmd( I2C2, ENABLE );

	I2C_AcknowledgeConfig( I2C2, ENABLE );
}

/**
  * @brief  等待 I2C 事件，带超时（65535 次轮询）
  * @param  I2Cx       I2C 外设基地址（I2C1 或 I2C2）
  * @param  I2C_EVENT  要等待的事件宏
  * @retval 0=事件到达，1=超时
  */
u8 IIC_WaitEvent(I2C_TypeDef* I2Cx, uint32_t I2C_EVENT){
    u16 counter = 0xffff;
    while( !I2C_CheckEvent( I2Cx, I2C_EVENT ) ){
        counter--;
        if(counter == 0){
            return 1;
        }
    }
    return 0;
}



/**
  * @brief  I2C 连续写入
  * @param  addr  从机 7 位地址
  * @param  reg   寄存器地址
  * @param  len   写入长度（字节）
  * @param  buf   数据缓冲区
  * @retval 0=成功，1=超时
  */
u8 IIC_WriteLen(u8 addr, u8 reg, u8 len, u8 *buf)
{
    u8 i = 0;

    I2C_AcknowledgeConfig(I2C2, ENABLE);
    I2C_GenerateSTART(I2C2, ENABLE);

    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_MODE_SELECT))
        return 1;
    I2C_Send7bitAddress(I2C2, (addr<<1) | 0, I2C_Direction_Transmitter); // 发送器件地址+写命令

    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_TRANSMITTER_MODE_SELECTED))
        return 1; // 等待应答

    while (I2C_GetFlagStatus(I2C2, I2C_FLAG_TXE) == RESET)
        ;
    I2C_SendData(I2C2, reg); // 写寄存器地址

    while (i < len)
    {
        if (I2C_GetFlagStatus(I2C2, I2C_FLAG_TXE) != RESET)
        {
            I2C_SendData(I2C2, buf[i]); // 发送数据
            i++;
        }
    }
    //    if(IIC_WaitEvent( I2C2, I2C_EVENT_MASTER_BYTE_TRANSMITTED ) )return 1;
    while (I2C_GetFlagStatus(I2C2, I2C_FLAG_TXE) == RESET)
        ;

    I2C_GenerateSTOP(I2C2, ENABLE);

    return 0;
}

/**
  * @brief  I2C 连续读取
  * @param  addr  从机 7 位地址
  * @param  reg   寄存器地址
  * @param  len   读取长度（字节）
  * @param  buf   数据缓冲区 [out]
  * @retval 0=成功，1=超时
  */
u8 IIC_ReadLen(u8 addr, u8 reg, u8 len, u8 *buf)
{
    u8 i = 0;

    I2C_AcknowledgeConfig(I2C2, ENABLE);
    I2C_GenerateSTART(I2C2, ENABLE);

    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_MODE_SELECT))return 1       ;
    I2C_Send7bitAddress(I2C2, (addr << 1) | 0X00, I2C_Direction_Transmitter); //发送器件地址+写命令

    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_TRANSMITTER_MODE_SELECTED))return 1       ; //等待应答

    I2C_SendData(I2C2, reg); //写寄存器地址

    I2C_GenerateSTART(I2C2, ENABLE);
    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_MODE_SELECT))return 1       ;

    I2C_Send7bitAddress(I2C2, ((addr << 1) | 0x01), I2C_Direction_Receiver); //发送器件地址+读命令
    if(IIC_WaitEvent(I2C2, I2C_EVENT_MASTER_RECEIVER_MODE_SELECTED))return 1       ; //等待应答

    while (i < len)
    {
        if (I2C_GetFlagStatus(I2C2, I2C_FLAG_RXNE) != RESET)
        {
            if (i == (len - 1))
            {
                I2C_AcknowledgeConfig(I2C2, DISABLE);
                buf[i] = I2C_ReceiveData(I2C2); //读数据,发送nACK
            }
            else
            {
                buf[i] = I2C_ReceiveData(I2C2); //读数据,发送ACK
            }
            i++;
        }
    }

    I2C_GenerateSTOP(I2C2, ENABLE); //产生一个停止条件

    return 0;
}


/**
 * @brief   I2C 读取单字节
 * @param   addr  从机 7 位地址
 * @param   reg   寄存器地址
 * @retval  读取到的数据（调用方需自行判断有效性）
 */
u8 IIC_ReadByte(u8 addr,u8 reg)
{
    u8 res;

    I2C_AcknowledgeConfig( I2C2, ENABLE );

    I2C_GenerateSTART( I2C2, ENABLE );

    while( !I2C_CheckEvent( I2C2, I2C_EVENT_MASTER_MODE_SELECT ) );
    I2C_Send7bitAddress(I2C2,(addr << 1) | 0X00,I2C_Direction_Transmitter); //发送器件地址+写命令

    if(IIC_WaitEvent( I2C2, I2C_EVENT_MASTER_TRANSMITTER_MODE_SELECTED ) )return 1;  //等待应答
    I2C_SendData(I2C2,reg);         //写寄存器地址

    I2C_GenerateSTART( I2C2, ENABLE );
    while( !I2C_CheckEvent( I2C2, I2C_EVENT_MASTER_MODE_SELECT ) );

    I2C_Send7bitAddress(I2C2,((addr << 1) | 0x01),I2C_Direction_Receiver);//发送器件地址+读命令
    while( !I2C_CheckEvent( I2C2, I2C_EVENT_MASTER_RECEIVER_MODE_SELECTED ) ); //等待应答

    I2C_AcknowledgeConfig( I2C2, DISABLE );

    while( I2C_GetFlagStatus( I2C2, I2C_FLAG_RXNE ) ==  RESET );
    res = I2C_ReceiveData( I2C2 ); //读数据,发送nACK


    I2C_GenerateSTOP( I2C2, ENABLE );//产生一个停止条件
    return res;
}


