/**
 * hx711.h - 4通道 HX711 驱动（STM32F103C8T6 / HAL库）
 *
 * 接线（每个称重传感器 -> 各自的 HX711 模块 A通道）：
 *   传感器 红(E+) -> HX711 E+      传感器 黑(E-) -> HX711 E-
 *   传感器 白(S+) -> HX711 A+      传感器 灰(S-) -> HX711 A-
 *   HX711 VCC -> 5V，GND 与 STM32 共地
 *   HX711 DT(数据) -> STM32 输入脚，HX711 SCK(时钟) -> STM32 输出脚
 */
#ifndef __HX711_H
#define __HX711_H

#include "stm32f1xx_hal.h"

#define HX711_CH_NUM   4            /* 传感器数量 */
#define HX711_ERR_VAL  0x7FFFFFFF   /* 读取超时返回值 */

typedef struct
{
    GPIO_TypeDef *dt_port;          /* DT 数据脚端口(输入) */
    uint16_t     dt_pin;
    GPIO_TypeDef *sck_port;         /* SCK 时钟脚端口(输出) */
    uint16_t     sck_pin;
} hx711_pin_t;

void    HX711_Init(void);                                   /* GPIO 初始化 */
int32_t HX711_ReadOne(uint8_t ch);                          /* 读单通道原始值，超时返回 HX711_ERR_VAL */
uint8_t HX711_ReadAll(int32_t out[HX711_CH_NUM]);           /* 读全部4通道，全部成功返回1，任一超时返回0 */

#endif
