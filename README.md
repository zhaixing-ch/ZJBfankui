# ZJBfankui - 装甲板四通道称重系统

基于达妙 DM_MC02（STM32H723VGT6）+ 4× HX711 的装甲板四点受力检测系统：四角各接一只全桥称重传感器，实时输出各支点载荷，用于判定靶车装甲板上的命中位置与重量分布。

## 仓库结构

```
├── HX711_4ch_Scale/
│   ├── dm_mc02_test/        # DM_MC02 裸机固件（寄存器版，无 HAL）
│   │   ├── main.c           # 4通道 HX711 采集 + RTT 输出
│   │   ├── startup.c        # 启动代码（含 RTT 段初始化）
│   │   ├── link.ld          # 链接脚本（RTT 控制块固定在 0x24000000）
│   │   └── Makefile
│   ├── rtt_dashboard.py     # 实时可视化面板（纯标准库，单文件）
│   ├── armor_schematic.html # 装甲板传感器布局原理图（浏览器直接打开）
│   └── hx711.c/h, main.c    # HX711 驱动参考实现
├── target_console/          # 靶车控制台上位机
└── 靶车项目文档.md
```

## 硬件接线

主控：达妙 DM_MC02（HSE 24MHz，固件运行在复位默认 HSI 64MHz）。
4 个 HX711 模块 VCC/GND 统一从板载 SBUS 座（5V）供电，共地。

| 通道 | 传感器位置 | DT（数据） | SCK（时钟） | 板上接口 |
|------|-----------|-----------|------------|----------|
| CH1 | 角 1 | PA0  | PA2  | 舵机口 |
| CH2 | 角 2 | PE9  | PE13 | 舵机口 |
| CH3 | 角 3 | PE14 | PD15 | 顶面 GPIO 座 |
| CH4 | 角 4 | PE0  | PE1  | 顶面 GPIO 座 |

> DT 为 5V 信号，所选引脚均为 FT（5V 容忍）。注意 PE11 是 QSPI Flash 片选且挂在 BTB 转接板上，不可用作 GPIO。

## 固件

采集时序：等 DT 拉低 → 24 位 MSB 先行 + 第 25 个脉冲（A 通道 / 增益 128）→ 24 位补码符号扩展。上电后四通道首次同时有效时自动 TARE（以当时的装甲板空载值为零点），之后输出 `CHx:原始值/净值`。刷新率由 HX711 模块 RATE 引脚决定（接 GND=10SPS，接 VCC=80SPS）。

编译（需 arm-none-eabi-gcc 14+）：

```bash
cd HX711_4ch_Scale/dm_mc02_test
make            # 生成 firmware.bin / firmware.elf
```

烧录（J-Link V9，SWD）：

```bash
sudo openocd -f interface/jlink.cfg -c "transport select swd; adapter speed 4000" \
     -f target/stm32h7x.cfg \
     -c "program firmware.bin 0x08000000 verify reset exit"
```

数据输出走 SEGGER RTT（控制块固定在 0x24000000）：

```bash
openocd -f interface/jlink.cfg -c "transport select swd; adapter speed 4000" \
     -f target/stm32h7x.cfg \
     -c "init; reset run; rtt setup 0x24000000 4096 \"SEGGER RTT\"; rtt start; rtt server start 19021 0"

# 另开终端读取
timeout 6 bash -c 'exec 3<>/dev/tcp/127.0.0.1/19021; cat <&3'
```

## 可视化面板

```bash
python3 HX711_4ch_Scale/rtt_dashboard.py
# 浏览器打开 http://localhost:8088
```

功能：四通道净值大数字 / 原始值 / 在线状态 / 强度条 + 实时滚动曲线（SSE 推流，20Hz）。RTT 断线自动重连。

## 后续计划

- [ ] 挂已知重量标定，counts → kg 比例系数
- [ ] 四通道载荷解算重量分布与命中位置
- [ ] STM32 作 I2C2 从机（PB10/PB11，地址由 PA0/PA1/PA2 设定）接入靶车主控
