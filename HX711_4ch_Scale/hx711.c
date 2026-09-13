/**
 * hx711.c - 4通道 HX711 驱动（STM32F103C8T6 / HAL库）
 *
 * 引脚分配（刻意避开 PB3/PB4 等 JTAG 复用脚，无需 remap）：
 *   CH1: DT=PB0  SCK=PB1
 *   CH2: DT=PB5  SCK=PB6
 *   CH3: DT=PB7  SCK=PB8
 *   CH4: DT=PB9  SCK=PB10
 */
#include "hx711.h"

static const hx711_pin_t hx_pins[HX711_CH_NUM] =
{
    { GPIOB, GPIO_PIN_0,  GPIOB, GPIO_PIN_1  },
    { GPIOB, GPIO_PIN_5,  GPIOB, GPIO_PIN_6  },
    { GPIOB, GPIO_PIN_7,  GPIOB, GPIO_PIN_8  },
    { GPIOB, GPIO_PIN_9,  GPIOB, GPIO_PIN_10 },
};

/* 微秒级粗延时，SCK 高电平只需 0.2~50us，要求很宽松 */
static void hx_delay_us(uint32_t us)
{
    uint32_t n = us * (SystemCoreClock / 1000000U) / 6U;
    while (n--) { __NOP(); }
}

void HX711_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* SCK：推挽输出，默认低电平（HX711 处于正常工作态） */
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    for (uint8_t i = 0; i < HX711_CH_NUM; i++)
    {
        gpio.Pin = hx_pins[i].sck_pin;
        HAL_GPIO_Init(hx_pins[i].sck_port, &gpio);
        HAL_GPIO_WritePin(hx_pins[i].sck_port, hx_pins[i].sck_pin, GPIO_PIN_RESET);
    }

    /* DT：上拉输入（数据未就绪时模块输出高电平） */
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    for (uint8_t i = 0; i < HX711_CH_NUM; i++)
    {
        gpio.Pin = hx_pins[i].dt_pin;
        HAL_GPIO_Init(hx_pins[i].dt_port, &gpio);
    }
}

/* 读一个通道：24位有符号原始值 + 第25个脉冲设定下次转换为A通道/128倍增益 */
int32_t HX711_ReadOne(uint8_t ch)
{
    const hx711_pin_t *p = &hx_pins[ch];
    int32_t raw = 0;
    uint32_t t0 = HAL_GetTick();

    /* 等待 DT 拉低（转换完成），10SPS 时最长约 100ms */
    while (HAL_GPIO_ReadPin(p->dt_port, p->dt_pin) == GPIO_PIN_SET)
    {
        if (HAL_GetTick() - t0 > 150)
        {
            return HX711_ERR_VAL;       /* 模块未接或故障 */
        }
    }

    __disable_irq();                    /* 时序期间关中断，保证脉宽稳定 */
    for (uint8_t i = 0; i < 24; i++)
    {
        HAL_GPIO_WritePin(p->sck_port, p->sck_pin, GPIO_PIN_SET);
        hx_delay_us(2);
        raw <<= 1;
        if (HAL_GPIO_ReadPin(p->dt_port, p->dt_pin) == GPIO_PIN_SET)
        {
            raw |= 1;
        }
        HAL_GPIO_WritePin(p->sck_port, p->sck_pin, GPIO_PIN_RESET);
        hx_delay_us(2);
    }
    /* 第25个脉冲：增益128、通道A（下次读数仍为传感器通道） */
    HAL_GPIO_WritePin(p->sck_port, p->sck_pin, GPIO_PIN_SET);
    hx_delay_us(2);
    HAL_GPIO_WritePin(p->sck_port, p->sck_pin, GPIO_PIN_RESET);
    __enable_irq();

    /* 24位二进制补码 -> 32位符号扩展 */
    if (raw & 0x800000)
    {
        raw |= 0xFF000000;
    }
    return raw;
}

/* 连续读4通道；任一通道超时返回0（本次数据作废） */
uint8_t HX711_ReadAll(int32_t out[HX711_CH_NUM])
{
    for (uint8_t i = 0; i < HX711_CH_NUM; i++)
    {
        out[i] = HX711_ReadOne(i);
        if (out[i] == HX711_ERR_VAL)
        {
            return 0;
        }
    }
    return 1;
}
