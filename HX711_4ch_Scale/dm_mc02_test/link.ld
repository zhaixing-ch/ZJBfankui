/* link.ld - STM32H723VGT6: 1MB Flash @0x08000000, 128KB DTCM @0x20000000 */
ENTRY(Reset_Handler)

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K
    DTCM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
    AXISRAM (rwx): ORIGIN = 0x24000000, LENGTH = 320K
}

SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH

    .text :
    {
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    _sidata = LOADADDR(.data);

    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > DTCM AT> FLASH

    .bss (NOLOAD) :
    {
        . = ALIGN(4);
        _sbss = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > DTCM

    /* RTT 控制块固定放在 AXISRAM 起始，便于 openocd/J-Link 定位 */
    .rtt :
    {
        . = ALIGN(16);
        _srtt = .;
        *(.rtt*)
        . = ALIGN(4);
        _ertt = .;
    } > AXISRAM AT> FLASH
    _lortt = LOADADDR(.rtt);

    .rttbuf (NOLOAD) : { *(.rttbuf*) } > AXISRAM

    _estack = ORIGIN(DTCM) + LENGTH(DTCM);
}
