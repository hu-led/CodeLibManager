#include "usart.h"

char          USART_RxPacket[USART_RX_BUF_SIZE];
volatile int  USART_RxOver = 0;

static volatile int  rx_cnt   = 0;
static volatile int  rx_state = 0;

static void usart_enable_clock(USART_TypeDef *usart)
{
         if (usart == USART1) RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    else if (usart == USART2) RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART2, ENABLE);
    else if (usart == USART3) RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);
}

/**
  * @brief  初始化 USART（TX+RX，RXNE 中断，8-N-1）
  * @note   自动根据 USART_INST 配置 TX/RX 引脚、RCC 时钟、NVIC
  *         printf 重定向由 debug.h 的 _write 提供，无需额外配置
  */
void USART_Host_Init(void)
{
    GPIO_InitTypeDef  gpio = {0};
    USART_InitTypeDef uart = {0};
    NVIC_InitTypeDef  nvic = {0};

    GPIO_TypeDef *tx_port, *rx_port;
    uint16_t      tx_pin,   rx_pin;
    uint32_t      rcc_gpio;
    uint8_t       irq_ch;

    /* ── 查表：USARTx → TX/RX 引脚 ── */
    if (USART_INST == USART1)
    {
        tx_port = GPIOA; tx_pin = GPIO_Pin_9;
        rx_port = GPIOA; rx_pin = GPIO_Pin_10;
        rcc_gpio = RCC_APB2Periph_GPIOA;
        irq_ch   = USART1_IRQn;
    }
    else if (USART_INST == USART2)
    {
        tx_port = GPIOA; tx_pin = GPIO_Pin_2;
        rx_port = GPIOA; rx_pin = GPIO_Pin_3;
        rcc_gpio = RCC_APB2Periph_GPIOA;
        irq_ch   = USART2_IRQn;
    }
    else /* USART3 */
    {
        tx_port = GPIOB; tx_pin = GPIO_Pin_10;
        rx_port = GPIOB; rx_pin = GPIO_Pin_11;
        rcc_gpio = RCC_APB2Periph_GPIOB;
        irq_ch   = USART3_IRQn;
    }

    /* ── 时钟 ── */
    usart_enable_clock(USART_INST);
    RCC_APB2PeriphClockCmd(rcc_gpio, ENABLE);

    /* ── GPIO ── */
    gpio.GPIO_Speed = GPIO_Speed_50MHz;

    gpio.GPIO_Pin  = tx_pin;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(tx_port, &gpio);

    gpio.GPIO_Pin  = rx_pin;
    gpio.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_Init(rx_port, &gpio);

    /* ── USART ── */
    uart.USART_BaudRate            = USART_BAUD;
    uart.USART_WordLength          = USART_WordLength_8b;
    uart.USART_StopBits            = USART_StopBits_1;
    uart.USART_Parity              = USART_Parity_No;
    uart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    uart.USART_Mode                = USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART_INST, &uart);

    USART_ITConfig(USART_INST, USART_IT_RXNE, ENABLE);

    /* ── NVIC ── */
    nvic.NVIC_IRQChannel                   = irq_ch;
    nvic.NVIC_IRQChannelPreemptionPriority = 1;
    nvic.NVIC_IRQChannelSubPriority        = 1;
    nvic.NVIC_IRQChannelCmd                = ENABLE;
    NVIC_Init(&nvic);

    USART_Cmd(USART_INST, ENABLE);
}

/**
  * @brief  发送一个字节（阻塞，等 TXE）
  */
void USART_SendByte(uint8_t byte)
{
    while (USART_GetFlagStatus(USART_INST, USART_FLAG_TC) == RESET);
    USART_SendData(USART_INST, byte);
}

/**
  * @brief  发送字节数组
  */
void USART_SendArray(uint8_t *arr, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++)
        USART_SendByte(arr[i]);
}

/**
  * @brief  发送字符串（以 '\0' 结尾）
  */
void USART_SendString(char *str)
{
    while (*str)
        USART_SendByte(*str++);
}

static uint32_t usart_pow10(uint8_t n)
{
    uint32_t r = 1;
    while (n--) r *= 10;
    return r;
}

/**
  * @brief  发送数字（按指定位宽，高位补空格）
  * @param  num    数字（0 - 4294967295）
  * @param  len    位宽（1 - 10）
  */
void USART_SendNumber(uint32_t num, uint8_t len)
{
    for (uint8_t i = 0; i < len; i++)
        USART_SendByte(num / usart_pow10(len - i - 1) % 10 + '0');
}

/**
  * @brief  格式化串口输出（不依赖 newlib，无 %f 限制）
  * @note   使用 vsprintf，newlib-nano 默认不支持 %f。浮点数请先转为整数。
  */
void USART_Printf(char *format, ...)
{
    char buf[128];
    va_list arg;
    va_start(arg, format);
    vsprintf(buf, format, arg);
    va_end(arg);
    USART_SendString(buf);
}

/**
  * @brief  RX 中断处理（用户在 USARTx_IRQHandler 中调用）
  * @note   以 "\r\n" 结尾的完整数据包存入 USART_RxPacket，置 USART_RxOver=1。
  *         范例：
  *         void USART1_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")))
  *         {
  *             if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
  *             {
  *                 USART_RxHandler(USART_ReceiveData(USART1));
  *                 USART_ClearITPendingBit(USART1, USART_IT_RXNE);
  *             }
  *         }
  */
void USART_RxHandler(uint8_t byte)
{
    if (byte == '\r')
    {
        /* \r: 视作包结束，忽略紧随的 \n */
        USART_RxPacket[rx_cnt] = '\0';
        rx_cnt   = 0;
        USART_RxOver = 1;
        rx_state = 1;  /* 跳过后续 \n */
        return;
    }
    if (byte == '\n')
    {
        if (rx_state == 1) { rx_state = 0; return; }  /* \r\n 中的 \n，忽略 */
        /* 独立的 \n 也视作包结束 */
        USART_RxPacket[rx_cnt] = '\0';
        rx_cnt   = 0;
        USART_RxOver = 1;
        return;
    }
    rx_state = 0;
    if (rx_cnt < USART_RX_BUF_SIZE - 1)
        USART_RxPacket[rx_cnt++] = byte;
}
