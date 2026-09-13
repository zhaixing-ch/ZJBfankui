/**
 * main.c - DM_MC02 (STM32H723VGT6) 4路 HX711 测试固件（裸机寄存器版）
 *
 * 接线（4×HX711，每个模块各自接一只全桥传感器：红->E+ 黑->E- 白->A+ 灰->A-）：
 *   CH1: DT=PA0  SCK=PA2     （舵机口）
 *   CH2: DT=PE9  SCK=PE13    （舵机口）
 *   CH3: DT=PE14 SCK=PD15    （顶面 GPIO 座；PE11 是 QSPI Flash 片选在 BTB 转接板上，不能用）
 *   CH4: DT=PE0  SCK=PE1     （顶面 GPIO 座，UART8 直连脚）
 *   电源：SBUS座 5V/GND 分配给 4 个模块（VCC=5V；PE14/PD15/PE0/PE1 均为 FT 脚可承受 5V DT）
 *
 * 输出：RTT（openocd rtt server 19021；USART1 引脚已让给 HX711，串口输出删除）
 *
 * 时钟：复位后默认 HSI 64MHz
 */
#include <stdint.h>

/* ---------------- 寄存器定义（最小集） ---------------- */
#define RCC_AHB4ENR   (*(volatile uint32_t *)0x580244E0UL)

#define GPIOA_BASE    0x58020000UL
#define GPIOC_BASE    0x58020800UL
#define GPIOD_BASE    0x58020C00UL
#define GPIOE_BASE    0x58021000UL

#define GPIO_MODER(b) (*(volatile uint32_t *)((b) + 0x00))
#define GPIO_PUPDR(b) (*(volatile uint32_t *)((b) + 0x0C))
#define GPIO_IDR(b)   (*(volatile uint32_t *)((b) + 0x10))
#define GPIO_BSRR(b)  (*(volatile uint32_t *)((b) + 0x18))
#define GPIO_AFRL(b)  (*(volatile uint32_t *)((b) + 0x20))
#define GPIO_AFRH(b)  (*(volatile uint32_t *)((b) + 0x24))

#define FLASH_ACR     (*(volatile uint32_t *)0x52002000UL)

/* ---------------- SEGGER RTT（openocd 可直接读取） ---------------- */
typedef struct {
    const char *name;
    char *buf;
    uint32_t size;
    volatile uint32_t wr;
    volatile uint32_t rd;
    int32_t flags;
} rtt_buf_t;

typedef struct {
    char id[16];
    int32_t max_up;
    int32_t max_down;
    rtt_buf_t up[2];
    rtt_buf_t down[2];
} rtt_cb_t;

__attribute__((used, section(".rtt"), aligned(16)))
static rtt_cb_t g_rtt = {
    .id = "SEGGER RTT",
    .max_up = 2,
    .max_down = 2,
};

__attribute__((used, section(".rttbuf"), aligned(16)))
static char g_rtt_upbuf[2048];

static void rtt_init(void)
{
    g_rtt.up[0].name = "terminal";
    g_rtt.up[0].buf  = g_rtt_upbuf;
    g_rtt.up[0].size = sizeof(g_rtt_upbuf);
    g_rtt.up[0].wr   = 0;
    g_rtt.up[0].rd   = 0;
    g_rtt.up[0].flags = 0;
}

static void rtt_write(const char *s, uint32_t len)
{
    uint32_t wr = g_rtt.up[0].wr;
    for (uint32_t i = 0; i < len; i++)
    {
        uint32_t next = (wr + 1) % g_rtt.up[0].size;
        if (next == g_rtt.up[0].rd)   /* 满则覆盖最旧数据，保持最新读数可见 */
        {
            g_rtt.up[0].rd = (g_rtt.up[0].rd + 1) % g_rtt.up[0].size;
        }
        g_rtt.up[0].buf[wr] = s[i];
        wr = next;
    }
    g_rtt.up[0].wr = wr;
}

/* ---------------- 输出 ---------------- */
static uint32_t my_strlen(const char *s)
{
    uint32_t n = 0;
    while (s[n]) { n++; }
    return n;
}

static void print(const char *s)
{
    rtt_write(s, my_strlen(s));
}

static void print_i32(int32_t v)
{
    char buf[16], *p = buf + sizeof(buf) - 1;
    *p = '\0';
    uint32_t u = (v < 0) ? (uint32_t)(-v) : (uint32_t)v;
    do { *--p = '0' + (u % 10); u /= 10; } while (u);
    if (v < 0) { *--p = '-'; }
    print(p);
}

/* ---------------- 基础初始化 ---------------- */
static void clocks_gpio_init(void)
{
    /* 64MHz 下保守设 4WS + WRHIGHFREQ=2，无论如何都安全 */
    FLASH_ACR = (4UL << 0) | (2UL << 4);

    RCC_AHB4ENR |= (1UL << 0)                /* GPIOA */
                 | (1UL << 4)                /* GPIOE */
                 | (1UL << 3)                /* GPIOD */
                 | (1UL << 2);               /* GPIOC */
    (void)RCC_AHB4ENR;                       /* 时钟使能生效需读回（跨D1-D2总线桥） */

    /* PC15 拉高：使能扩展板 5V 输出（舵机口 5V 针可用） */
    GPIO_MODER(GPIOC_BASE) &= ~(3UL << (15 * 2));
    GPIO_MODER(GPIOC_BASE) |=  (1UL << (15 * 2));    /* 输出 */
    GPIO_BSRR(GPIOC_BASE)  = (1UL << 15);            /* 高 */

    /* PA0: 输入上拉（CH1 DT），PA2: 输出低（CH1 SCK） */
    GPIO_MODER(GPIOA_BASE) &= ~(3UL << (0 * 2));
    GPIO_PUPDR(GPIOA_BASE) &= ~(3UL << (0 * 2));
    GPIO_PUPDR(GPIOA_BASE) |=  (1UL << (0 * 2));     /* 上拉 */
    GPIO_MODER(GPIOA_BASE) &= ~(3UL << (2 * 2));
    GPIO_MODER(GPIOA_BASE) |=  (1UL << (2 * 2));     /* PA2 输出 */
    GPIO_BSRR(GPIOA_BASE)  = (1UL << 2) << 16;       /* SCK = 低（高>60us HX711会掉电） */

    /* PE9: 输入上拉（CH2 DT），PE13: 输出低（CH2 SCK）
     * PE14: 输入上拉（CH3 DT），PE0: 输入上拉（CH4 DT），PE1: 输出低（CH4 SCK） */
    GPIO_PUPDR(GPIOE_BASE) &= ~((3UL << (9 * 2)) | (3UL << (14 * 2)) | (3UL << (0 * 2)));
    GPIO_PUPDR(GPIOE_BASE) |=  (1UL << (9 * 2)) | (1UL << (14 * 2)) | (1UL << (0 * 2));
    GPIO_MODER(GPIOE_BASE) &= ~((3UL << (9 * 2)) | (3UL << (14 * 2)) | (3UL << (0 * 2)));
    GPIO_MODER(GPIOE_BASE) &= ~((3UL << (13 * 2)) | (3UL << (1 * 2)));
    GPIO_MODER(GPIOE_BASE) |=  (1UL << (13 * 2)) | (1UL << (1 * 2));
    GPIO_BSRR(GPIOE_BASE)  = ((1UL << 13) | (1UL << 1)) << 16;

    /* PD15: 输出低（CH3 SCK；高>60us HX711会掉电） */
    GPIO_MODER(GPIOD_BASE) &= ~(3UL << (15 * 2));
    GPIO_MODER(GPIOD_BASE) |=  (1UL << (15 * 2));
    GPIO_BSRR(GPIOD_BASE)  = (1UL << 15) << 16;
}

static void delay_ms(uint32_t ms)
{
    /* 64MHz，NOP 循环约 6 周期/次 */
    uint32_t n = ms * (64UL * 1000UL / 6UL);
    while (n--) { __asm volatile ("nop"); }
}

/* ---------------- HX711 4通道 ---------------- */
typedef struct {
    uint32_t dt_base, dt_pin;
    uint32_t sck_base, sck_pin;
} hx_pin_t;

static const hx_pin_t hx[4] =
{
    { GPIOA_BASE, 1UL << 0,  GPIOA_BASE, 1UL << 2  },  /* CH1: PA0/PA2  */
    { GPIOE_BASE, 1UL << 9,  GPIOE_BASE, 1UL << 13 },  /* CH2: PE9/PE13 */
    { GPIOE_BASE, 1UL << 14, GPIOD_BASE, 1UL << 15 },  /* CH3: PE14/PD15 */
    { GPIOE_BASE, 1UL << 0,  GPIOE_BASE, 1UL << 1  },  /* CH4: PE0/PE1 */
};

#define HX_ERR  0x7FFFFFFF

static int32_t hx711_read(uint8_t ch)
{
    const hx_pin_t *p = &hx[ch];
    int32_t raw = 0;
    uint32_t t0 = 0;

    /* 等 DT 拉低（转换完成，10SPS 最长约100ms） */
    while (GPIO_IDR(p->dt_base) & p->dt_pin)
    {
        delay_ms(1);
        if (++t0 > 300) { return HX_ERR; }
    }

    for (int i = 0; i < 24; i++)
    {
        GPIO_BSRR(p->sck_base) = p->sck_pin;
        for (volatile int d = 0; d < 20; d++) { }        /* ~2us */
        raw <<= 1;
        if (GPIO_IDR(p->dt_base) & p->dt_pin) { raw |= 1; }
        GPIO_BSRR(p->sck_base) = p->sck_pin << 16;
        for (volatile int d = 0; d < 20; d++) { }
    }
    /* 第25个脉冲：下次转换 A 通道、增益128 */
    GPIO_BSRR(p->sck_base) = p->sck_pin;
    for (volatile int d = 0; d < 20; d++) { }
    GPIO_BSRR(p->sck_base) = p->sck_pin << 16;

    if (raw & 0x800000) { raw |= (int32_t)0xFF000000; }
    return raw;
}

/* ---------------- main ---------------- */
int main(void)
{
    rtt_init();
    clocks_gpio_init();
    delay_ms(100);

    print("\r\n=== 4x HX711 @ DM_MC02 ===\r\n");
    print("CH1:PA0/PA2 CH2:PE9/PE13 CH3:PE14/PD15 CH4:PE0/PE1\r\n");

    int32_t tare[4] = {0, 0, 0, 0};
    uint8_t tared = 0;
    uint32_t err_cnt[4] = {0, 0, 0, 0};

    for (;;)
    {
        int32_t raw[4];
        uint8_t ok = 0;

        for (uint8_t ch = 0; ch < 4; ch++)
        {
            raw[ch] = hx711_read(ch);
            if (raw[ch] != HX_ERR) { ok |= (1 << ch); }
        }

        /* 四通道首次全部有效时记录零点 */
        if (!tared && ok == 0x0F)
        {
            for (uint8_t ch = 0; ch < 4; ch++) { tare[ch] = raw[ch]; }
            tared = 1;
            print("[TARE] 已记录四通道零点\r\n");
        }

        /* 输出：每通道一行原始值+净值；离线通道报错 */
        for (uint8_t ch = 0; ch < 4; ch++)
        {
            if (raw[ch] == HX_ERR)
            {
                err_cnt[ch]++;
                if (err_cnt[ch] <= 3)     /* 每通道只报前3次，避免刷屏 */
                {
                    print("ERR: CH");
                    print_i32(ch + 1);
                    print(" 离线(DT高)，查该模块供电/接线\r\n");
                }
            }
        }

        if (ok != 0)
        {
            for (uint8_t ch = 0; ch < 4; ch++)
            {
                print("CH");
                print_i32(ch + 1);
                print(":");
                if (raw[ch] == HX_ERR) { print("OFF      "); }
                else
                {
                    print_i32(raw[ch]);
                    print("/");
                    if (tared) { print_i32(raw[ch] - tare[ch]); }
                    else       { print("TARE.."); }
                    print("  ");
                }
            }
            print("\r\n");
        }

        /* 不加固定延时：数据一到就输出，实际速率由HX711采样率决定
         * （RATE引脚接GND=10SPS，接VCC=80SPS，模块硬件决定） */
    }
}
