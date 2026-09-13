# Makefile - DM_MC02 HX711 测试固件
CROSS  = arm-none-eabi-
CC     = $(CROSS)gcc
OBJCOPY= $(CROSS)objcopy
MCU    = -mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard
CFLAGS = $(MCU) -O2 -Wall -ffreestanding -nostdlib -fno-builtin

OBJS = startup.o main.o

all: firmware.elf firmware.bin

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

firmware.elf: $(OBJS) link.ld
	$(CC) $(CFLAGS) -T link.ld $(OBJS) -o $@ --specs=nosys.specs -lgcc

firmware.bin: firmware.elf
	$(OBJCOPY) -O binary $< $@

flash: firmware.bin
	openocd -f interface/jlink.cfg -c "transport select swd; adapter speed 4000" \
	        -f target/stm32h7x.cfg \
	        -c "program firmware.bin 0x08000000 verify reset exit"

rtt: firmware.elf
	openocd -f interface/jlink.cfg -c "transport select swd; adapter speed 4000" \
	        -f target/stm32h7x.cfg \
	        -c "init; reset run; rtt setup 0x24000000 4096 \"SEGGER RTT\"; rtt start; rtt server start 19021 0"

clean:
	rm -f *.o firmware.elf firmware.bin firmware.map

.PHONY: all flash rtt clean
