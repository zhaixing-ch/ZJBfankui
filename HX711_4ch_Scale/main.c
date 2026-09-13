/**
 * main.c - 四传感器共秤台称重（4×HX711 + STM32F103C8T6，HAL库）
 *
 * 硬件：
 *   4个称重传感器分别接 4 个 HX711 的 E+/E-/A+/A-（见 hx711.h 顶部说明）
 *   HX711 引脚见 hx711.c 顶部（PB0/PB1/PB5/PB6/PB7/PB8/PB9/PB10）
 *   串口1: PA9(TX) -> USB转TTL 的 RX，115200-8-N-1，共地
 *
 * 使用流程（串口命令）：
 *   1. 秤台空载，发送 't'  -> 去皮（记录零点）
 *   2. 放上已知重量的砝码（改下方 CAL_WEIGHT_G，默认1000g），发送 'c' -> 标定
 *   3. 串口会打印标定系数，把它填到下面的 CAL_FACTOR_DEFAULT，下次上电免标定
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hx711.h"

/* ---------------- 可调参数 ---------------- */
#define SAMPLE_N           5        /* 每通道滤波采样数（10SPS时约0.5s出一组数） */
#define CAL_WEIGHT_G       1000.0f  /* 标定砝码克数 */
#define CAL_FACTOR_DEFAULT 8000.0f  /* 默认标定系数 = 4通道raw之和 每 1g（标定后更新） */
/* ------------------------------------------ */

UART_HandleTypeDef huart1;
static uint8_t rx_byte, rx_cmd = 0;

static float g_cal_factor = CAL_FACTOR_DEFAULT;
static int32_t g_tare_raw = 0;      /* 空载时4通道raw之和 */

/* ================= 时钟：HSE 8MHz x9 = 72MHz ================= */
static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLMUL = RCC_PLL_MUL9;
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) { Error_Handler(); }

    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                  | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2) != HAL_OK) { Error_Handler(); }
}

/* ================= 串口1：PA9 TX / PA10 RX ================= */
static void USART1_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    /* TX 复用推挽 */
    gpio.Pin = GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &gpio);
    /* RX 浮空输入 */
    gpio.Pin = GPIO_PIN_10;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&huart1) != HAL_OK) { Error_Handler(); }

    /* 开接收中断，用于接收串口命令 */
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
}

/* printf 重定向：Keil(MicroLib) 与 GCC 都支持 */
int fputc(int ch, FILE *f)
{
    (void)f;
    uint8_t c = (uint8_t)ch;
    HAL_UART_Transmit(&huart1, &c, 1, 10);
    return ch;
}
int __io_putchar(int ch) { return fputc(ch, NULL); }

/* 串口命令回调 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        rx_cmd = rx_byte;
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}

/* ================ 数据处理 ================ */

/* 排序取中段平均：去掉最大最小后取平均，抗脉冲干扰 */
static int32_t filter_avg(int32_t *a, int n)
{
    int64_t sum = 0;
    for (int i = 0; i < n - 1; i++)         /* 简单冒泡，n很小无所谓 */
    {
        for (int j = 0; j < n - 1 - i; j++)
        {
            if (a[j] > a[j + 1])
            {
                int32_t t = a[j]; a[j] = a[j + 1]; a[j + 1] = t;
            }
        }
    }
    for (int i = 1; i < n - 1; i++)         /* 去掉首尾 */
    {
        sum += a[i];
    }
    return (int32_t)(sum / (n - 2));
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    USART1_Init();
    HX711_Init();

    printf("\r\n=== 4xHX711 秤台称重 ===\r\n");
    printf("命令: t=去皮  c=标定(%dg)\r\n", (int)CAL_WEIGHT_G);

    int32_t raw[HX711_CH_NUM];
    int32_t buf[HX711_CH_NUM][SAMPLE_N] = {0};
    uint8_t cnt = 0;
    uint32_t last_print = 0;

    /* 上电先读一次零点，避免开机显示乱跳 */
    HAL_Delay(500);
    if (HX711_ReadAll(raw))
    {
        g_tare_raw = raw[0] + raw[1] + raw[2] + raw[3];
    }

    while (1)
    {
        /* 读4通道并滤波 */
        if (HX711_ReadAll(raw))
        {
            for (uint8_t i = 0; i < HX711_CH_NUM; i++)
            {
                buf[i][cnt] = raw[i];
            }
            cnt = (cnt + 1) % SAMPLE_N;
        }
        else
        {
            printf("ERR: HX711 offline!\r\n");   /* 有模块没接好 */
            HAL_Delay(500);
            continue;
        }

        /* 串口命令处理 */
        if (rx_cmd == 't')
        {
            rx_cmd = 0;
            g_tare_raw = 0;
            for (uint8_t i = 0; i < HX711_CH_NUM; i++)
            {
                g_tare_raw += filter_avg(buf[i], SAMPLE_N);
            }
            printf("[TARE] 零点=%ld\r\n", (long)g_tare_raw);
        }
        else if (rx_cmd == 'c')
        {
            rx_cmd = 0;
            int32_t now = 0;
            for (uint8_t i = 0; i < HX711_CH_NUM; i++)
            {
                now += filter_avg(buf[i], SAMPLE_N);
            }
            g_cal_factor = (float)(now - g_tare_raw) / CAL_WEIGHT_G;
            printf("[CAL] 系数=%.1f raw/g (填入 CAL_FACTOR_DEFAULT 可免标定)\r\n",
                   (double)g_cal_factor);
        }

        /* 每500ms输出一次重量 */
        if (HAL_GetTick() - last_print >= 500)
        {
            last_print = HAL_GetTick();

            int32_t sum = 0;
            int32_t each[HX711_CH_NUM];
            for (uint8_t i = 0; i < HX711_CH_NUM; i++)
            {
                each[i] = filter_avg(buf[i], SAMPLE_N);
                sum += each[i];
            }

            float weight_g = (float)(sum - g_tare_raw) / g_cal_factor;
            printf("CH1:%-9ld CH2:%-9ld CH3:%-9ld CH4:%-9ld | %6.1f g\r\n",
                   (long)each[0], (long)each[1], (long)each[2], (long)each[3],
                   (double)weight_g);
        }
    }
}

void Error_Handler(void)
{
    __disable_irq();
    while (1) { }
}
