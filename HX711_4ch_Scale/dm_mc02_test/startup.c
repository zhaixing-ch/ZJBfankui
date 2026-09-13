/* startup.c - STM32H723 最小启动代码（无 HAL，无 libc 依赖） */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern uint32_t _lortt, _srtt, _ertt;

int main(void);

void Reset_Handler(void) __attribute__((noreturn));
void Default_Handler(void) __attribute__((noreturn));

__attribute__((used, section(".isr_vector")))
const void *vector_table[] = {
    (void *)&_estack,   /* 初始栈指针 */
    Reset_Handler,      /* Reset */
    Default_Handler,    /* NMI */
    Default_Handler,    /* HardFault */
    Default_Handler,    /* MemManage */
    Default_Handler,    /* BusFault */
    Default_Handler,    /* UsageFault */
    0, 0, 0, 0,
    Default_Handler,    /* SVC */
    Default_Handler,    /* DebugMon */
    0,
    Default_Handler,    /* PendSV */
    Default_Handler,    /* SysTick */
};

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; ) { *dst++ = *src++; }
    for (uint32_t *dst = &_sbss; dst < &_ebss; )  { *dst++ = 0; }

    /* RTT 控制块（AXISRAM），初始化数据从 Flash 拷贝 */
    src = &_lortt;
    for (uint32_t *dst = &_srtt; dst < &_ertt; ) { *dst++ = *src++; }

    /* 中断向量表映射到 Flash */
    *(volatile uint32_t *)0xE000ED08 = 0x08000000;  /* SCB->VTOR */

    main();
    while (1) { }
}

void Default_Handler(void)
{
    while (1) { }
}
