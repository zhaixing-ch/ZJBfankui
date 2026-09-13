#!/usr/bin/env python3
"""生成嘉立创EDA专业版(Pro)原理图 JSON：装甲板受击检测节点
4×薄膜压敏 + 4×HX711 + STM32F103C8T6 (I2C2从机, ID焊盘设定)
格式参照真实 Pro 工程文件结构 (docType 5)。
"""
import json, uuid, time

def gid():
    return "gge" + uuid.uuid4().hex[:8]

shapes = []

# ---------- 图元 ----------
def W(x1, y1, x2, y2):
    if abs(x1 - x2) < 0.5 and abs(y1 - y2) < 0.5:
        return  # 跳过零长度导线
    shapes.append(f"W~{x1} {y1} {x2} {y2}~#008800~1~0~none~{gid()}~0")

def _clean(s):
    return str(s).replace("~", "-")

def N(x, y, name, tx=None, ty=None, color="#0000ff"):
    name = _clean(name)
    tx = x if tx is None else tx
    ty = y - 4 if ty is None else ty
    shapes.append(f"N~{x}~{y}~0~{color}~{name}~{gid()}~start~{tx}~{ty}~Times New Roman~7pt~0")

def J(x, y):
    shapes.append(f"J~{x}~{y}~2.5~#CC0000~{gid()}~0")

def O(x, y):
    shapes.append(f"O~{x}~{y}~{gid()}~M {x-4} {y-4} L {x+4} {y+4} M {x+4} {y-4} L {x-4} {y+4}~#33cc33~0")

def F_VCC(x, y, name="VCC"):
    kind = "part_netLabel_VCC" if name == "VCC" else "part_netLabel_" + name
    shapes.append(
        f"F~{kind}~{x}~{y}~0~{gid()}~~0^^{x}~{y}^^{name}~#000000~{x-12}~{y-12}~0~start~1~Times New Roman~9pt~{gid()}"
        f"^^PL~{x} {y-10} {x} {y}~#000000~1~0~transparent~{gid()}~0"
        f"^^PL~{x-5} {y-10} {x+5} {y-10}~#000000~1~0~transparent~{gid()}~0")

def F_GND(x, y):
    shapes.append(
        f"F~part_netLabel_gnD~{x}~{y}~0~{gid()}~~0^^{x}~{y}^^GND~#000000~{x-13}~{y+27.23}~0~start~1~Times New Roman~9pt~{gid()}"
        f"^^PL~{x} {y+10} {x} {y}~#000000~1~0~transparent~{gid()}~0"
        f"^^PL~{x-9} {y+10} {x+9} {y+10}~#000000~1~0~transparent~{gid()}~0"
        f"^^PL~{x-6} {y+14} {x+6} {y+14}~#000000~1~0~transparent~{gid()}~0"
        f"^^PL~{x-3} {y+18} {x+3} {y+18}~#000000~1~0~transparent~{gid()}~0")

def T(x, y, text, color="#000080"):
    shapes.append(f"T~N~{x}~{y}~0~{color}~Arial~~~~~comment~{_clean(text)}~1~start~{gid()}~0~")

# ---------- 引脚 ----------
def pin(num, name, ex, ey, side, edge):
    if side == "L":
        rot, path = 180, f"M {ex} {ey} h 10"
        nseg = f"1~{edge-0.5}~{ey-1}~0~{num}~end~~~#0000FF"
        nmeseg = f"1~{edge+3.7}~{ey-4}~0~{name}~start~~~#0000FF"
        dot, deco = f"0~{edge-3}~{ey}", f"0~M {edge} {ey+3} L {edge+3} {ey} L {edge} {ey-3}"
    elif side == "R":
        rot, path = 0, f"M {ex} {ey} h -10"
        nseg = f"1~{edge+0.5}~{ey-1}~0~{num}~start~~~#0000FF"
        nmeseg = f"1~{edge-3.7}~{ey-4}~0~{name}~end~~~#0000FF"
        dot, deco = f"0~{edge+3}~{ey}", f"0~M {edge} {ey+3} L {edge-3} {ey} L {edge} {ey-3}"
    elif side == "T":
        rot, path = 90, f"M {ex} {edge} v -10"
        nseg = f"1~{ex+3}~{edge-3}~0~{num}~start~~~#0000FF"
        nmeseg = f"1~{ex+3}~{edge+10}~0~{name}~start~~~#0000FF"
        dot, deco = f"0~{ex}~{edge-3}", f"0~M {ex-3} {edge} L {ex} {edge-3} L {ex+3} {edge}"
    else:  # B
        rot, path = 270, f"M {ex} {edge} v 10"
        nseg = f"1~{ex+3}~{edge+8}~0~{num}~start~~~#0000FF"
        nmeseg = f"1~{ex+3}~{edge-8}~0~{name}~start~~~#0000FF"
        dot, deco = f"0~{ex}~{edge+3}", f"0~M {ex-3} {edge} L {ex} {edge+3} L {ex+3} {edge}"
    return (f"P~show~0~{num}~{ex}~{ey}~{rot}~{gid()}~0^^{ex}~{ey}^^{path}~#880000"
            f"^^{nmeseg}^^{nseg}^^{dot}^^{deco}")

# ---------- 元件 ----------
def make_comp(ax, ay, ref, value, pre, pins, body=None, extra=None,
              mpn="?", pkg="NONE", lcsc=""):
    """pins: list of pin() 结果; body: (x,y,w,h); extra: 附加子形状
    lcsc: 立创编号, mpn: 制造商型号, pkg: 封装名（导入后供器件标准化匹配）"""
    subs = []
    if body:
        bx, by, bw, bh = body
        subs.append(f"R~{bx}~{by}~~~{bw}~{bh}~#880000~1~0~none~{gid()}~0~")
        subs.append(f"T~P~{bx}~{by-6}~0~#000080~Arial~~~~~comment~{ref}~1~start~{gid()}~0")
        subs.append(f"T~N~{bx}~{by+bh+12}~0~#000080~Arial~~~~~comment~{value}~1~start~{gid()}~0")
    subs += [p for p in pins]
    if extra:
        subs += extra
    attrs = (f"package`{pkg}`BOM_Manufacturer Part`{mpn}`Supplier Part`{lcsc}"
             f"`Supplier`{('LCSC' if lcsc else '')}`spicePre`{pre}`spiceSymbolName`{value}`")
    shapes.append(f"LIB~{ax}~{ay}~{attrs}~~0~{gid()}~{uuid.uuid4().hex}~{uuid.uuid4().hex}~0~~yes~yes~~{int(time.time())}~"
                  + "#@$" + "#@$".join(subs))

def comp2p(cx, cy, ref, value, pre="R", **kw):
    """水平2引脚元件，返回两端点"""
    pins = [pin("1", "1", cx-18, cy, "L", cx-8), pin("2", "2", cx+18, cy, "R", cx+8)]
    make_comp(cx, cy, ref, value, pre, pins, body=(cx-8, cy-5, 16, 10), **kw)
    return (cx-18, cy), (cx+18, cy)

# ============================================================
# 画原理图
# ============================================================
T(380, -20, "装甲板受击检测节点：4x薄膜压敏 + 4xHX711 + STM32F103C8T6 (I2C2从机, VCC=3.3V)", "#000080")

# ---- 电源部分 (左上) ----
# J2 电源输入 2P
pins = [pin("1", "5V", 110, -820, "L", 120), pin("2", "GND", 110, -790, "L", 120)]
make_comp(60, -840, "J2", "DC5V_IN", "J", pins, body=(60, -840, 60, 60),
          mpn="PZ254V-11-02P", pkg="HDR-TH_2P-P2.54")
F_GND(110, -790)
# U2 AMS1117-3.3
pins = [pin("3", "VIN", 180, -820, "L", 190), pin("1", "GND", 180, -795, "L", 190),
        pin("2", "VOUT", 290, -820, "R", 280)]
make_comp(190, -835, "U2", "AMS1117-3.3", "U", pins, body=(190, -835, 90, 50),
          lcsc="C6186", mpn="AMS1117-3.3", pkg="SOT-223")
W(110, -820, 180, -820)          # 5V -> VIN
W(180, -795, 160, -795); F_GND(160, -795)
W(290, -820, 330, -820); F_VCC(330, -830)   # VOUT -> VCC
# C1 输入 10uF
p1, p2 = comp2p(150, -740, "C1", "10uF", "C", lcsc="C15850",
                mpn="CL21A106KAYNNNE", pkg="C0805")
W(p1[0], p1[1], 132, -740); W(132, -740, 132, -820); J(132, -820)
W(p2[0], p2[1], 168, -740); W(168, -740, 168, -725); F_GND(168, -725)
# C2 输出 10uF
p1, p2 = comp2p(310, -740, "C2", "10uF", "C", lcsc="C15850",
                mpn="CL21A106KAYNNNE", pkg="C0805")
W(p1[0], p1[1], 292, -740); W(292, -740, 292, -820); J(292, -820)
W(p2[0], p2[1], 328, -740); W(328, -740, 328, -725); F_GND(328, -725)
F_VCC(60, -840, "+5V")  # 备用标签放低优先，改放 J2 上方
shapes.pop()  # 撤销上面这个，改为在 J2 5V 引脚放置
F_VCC(110, -830, "+5V")

# ---- 4 通道：传感器 + HX711 (左列) ----
for i, cy in enumerate([-700, -590, -480, -370], start=1):
    # RP 压敏传感器（外购薄膜传感器，无立创编号）
    p1, p2 = comp2p(60, cy, f"RP{i}", "RP-C18.3-ST", "RP", mpn="RP-C18.3-ST")
    # HX711 模块
    pins = [pin("1", "E+", 140, cy-25, "L", 150),
            pin("2", "A+", 140, cy,     "L", 150),
            pin("3", "A-", 140, cy+25,  "L", 150),
            pin("4", "DT", 290, cy-15,  "R", 280),
            pin("5", "SCK", 290, cy+15, "R", 280),
            pin("6", "VCC", 170, cy-50, "T", cy-40),
            pin("7", "GND", 260, cy+50, "B", cy+40)]
    make_comp(150, cy-40, f"U{i+2}", f"HX711 #{i}", "U", pins, body=(150, cy-40, 130, 80),
              mpn="HX711 module")
    # 接线
    W(p1[0], p1[1], 42, cy); W(42, cy, 42, cy-25); W(42, cy-25, 140, cy-25)  # 传感器->E+
    W(p2[0], p2[1], 140, cy)                                                  # 传感器->A+
    W(140, cy+25, 312, cy+25)                                                 # A- -> R
    pr1, pr2 = comp2p(330, cy+25, f"R{i}", "10k", "R", lcsc="C25804",
                      mpn="0603WAF1002T5E", pkg="R0603")
    W(pr2[0], pr2[1], 348, cy+25); W(348, cy+25, 348, cy+40); F_GND(348, cy+40)
    F_VCC(170, cy-60)
    F_GND(260, cy+50)
    N(290, cy-15, f"HX_DT{i}", tx=293, ty=cy-19)
    N(290, cy+15, f"HX_SCK{i}", tx=293, ty=cy+11)

# ---- U1 STM32F103C8T6 ----
BX, BY, BW, BH = 560, -700, 200, 330
mcu_pins = []
left_defs = [("18", "PB0/DT1", -675), ("19", "PB1/SCK1", -640), ("41", "PB5/DT2", -605),
             ("42", "PB6/SCK2", -570), ("43", "PB7/DT3", -535), ("45", "PB8/SCK3", -500),
             ("46", "PB9/DT4", -465), ("25", "PB12/SCK4", -430),
             ("5", "PD0/OSCI", -395), ("6", "PD1/OSCO", -360)]
right_defs = [("21", "PB10/SCL", -675), ("22", "PB11/SDA", -640), ("10", "PA0/ID0", -605),
              ("11", "PA1/ID1", -570), ("12", "PA2/ID2", -535), ("34", "PA13/SWDIO", -500),
              ("37", "PA14/SWCLK", -465), ("7", "NRST", -430), ("44", "BOOT0", -395)]
top_defs = [("24", "VDD_1", 600), ("36", "VDD_2", 630), ("48", "VDD_3", 660), ("9", "VDDA", 720)]
bot_defs = [("23", "VSS_1", 600), ("35", "VSS_2", 630), ("47", "VSS_3", 660), ("8", "VSSA", 720)]
for num, name, ey in left_defs:
    mcu_pins.append(pin(num, name, 550, ey, "L", 560))
for num, name, ey in right_defs:
    mcu_pins.append(pin(num, name, 770, ey, "R", 760))
for num, name, px in top_defs:
    mcu_pins.append(pin(num, name, px, -710, "T", -700))
for num, name, px in bot_defs:
    mcu_pins.append(pin(num, name, px, -360, "B", -370))
make_comp(560, -700, "U1", "STM32F103C8T6", "U", mcu_pins, body=(BX, BY, BW, BH),
          lcsc="C8734", mpn="STM32F103C8T6", pkg="LQFP-48")
T(560, -675, "LQFP48", "#808080")

# MCU 电源
for _, _, px in top_defs:
    F_VCC(px, -720)
for _, _, px in bot_defs:
    F_GND(px, -360)
# 左侧信号网络标签
for num, name, ey in left_defs:
    net = name.split("/")[1]
    N(550, ey, net, tx=505, ty=ey-4)
# 右侧
N(770, -675, "SCL", tx=773, ty=-679)
N(770, -640, "SDA", tx=773, ty=-644)
N(770, -500, "SWDIO", tx=773, ty=-504)
N(770, -465, "SWCLK", tx=773, ty=-469)
N(770, -430, "NRST", tx=773, ty=-434)
# BOOT0 -> R7 -> GND
W(770, -395, 812, -395)
pr1, pr2 = comp2p(830, -395, "R7", "10k", "R", lcsc="C25804",
                  mpn="0603WAF1002T5E", pkg="R0603")
W(pr2[0], pr2[1], 865, -395); F_GND(865, -395)

# ---- ID 设定焊盘 J3~J5 ----
for k, ey in enumerate([-605, -570, -535], start=0):
    W(770, ey, 840, ey)
    pins = [pin("1", "ID", 840, ey, "L", 850), pin("2", "GND", 910, ey, "R", 900)]
    make_comp(850, ey-15, f"J{k+3}", f"ID{k} 焊盘", "J", pins, body=(850, ey-15, 50, 30),
              mpn="PZ254V-11-02P", pkg="HDR-TH_2P-P2.54")
    F_GND(910, ey)

# ---- I2C 接口 J1 + 上拉 ----
pins = [pin("1", "VCC", 990, -675, "L", 1000), pin("2", "SCL", 990, -650, "L", 1000),
        pin("3", "SDA", 990, -625, "L", 1000), pin("4", "GND", 990, -600, "L", 1000)]
make_comp(1000, -700, "J1", "I2C_TO_HOST", "J", pins, body=(1000, -700, 60, 110),
          lcsc="C2691448", mpn="PZ254V-11-04P", pkg="HDR-TH_4P-P2.54")
F_VCC(990, -685)
F_GND(990, -600)
N(990, -650, "SCL", tx=940, ty=-654)
N(990, -625, "SDA", tx=940, ty=-629)
pr1, pr2 = comp2p(900, -720, "R5", "4.7k", "R", mpn="0603WAF4701T5E", pkg="R0603")
F_VCC(pr1[0], pr1[1]-10); N(pr2[0], pr2[1], "SCL", tx=921, ty=-724)
pr1, pr2 = comp2p(900, -560, "R6", "4.7k", "R", mpn="0603WAF4701T5E", pkg="R0603")
F_VCC(pr1[0], pr1[1]-10); N(pr2[0], pr2[1], "SDA", tx=921, ty=-564)

# ---- 晶振 + 负载电容 (网络标签连接) ----
p1, p2 = comp2p(400, -760, "Y1", "8MHz", "Y", lcsc="C251585",
                mpn="7U08000E10UCG", pkg="SMD5032-2P")
N(p1[0], p1[1], "OSCI", tx=p1[0]-42, ty=p1[1]-4)
N(p2[0], p2[1], "OSCO", tx=p2[0]+3, ty=p2[1]-4)
p1, p2 = comp2p(400, -810, "C3", "20pF", "C", mpn="CL10C200JB8NNNC", pkg="C0603")
N(p1[0], p1[1], "OSCI", tx=p1[0]-42, ty=p1[1]-4)
W(p2[0], p2[1], 428, -810); W(428, -810, 428, -795); F_GND(428, -795)
p1, p2 = comp2p(470, -810, "C4", "20pF", "C", mpn="CL10C200JB8NNNC", pkg="C0603")
N(p1[0], p1[1], "OSCO", tx=p1[0]-42, ty=p1[1]-4)
W(p2[0], p2[1], 498, -810); W(498, -810, 498, -795); F_GND(498, -795)

# ---- MCU 去耦 ----
p1, p2 = comp2p(830, -300, "C5", "100nF", "C", lcsc="C14663",
                mpn="CC0603KRX7R9BB104", pkg="C0603")
F_VCC(p1[0], p1[1]-10); F_GND(p2[0], p2[1])
p1, p2 = comp2p(900, -300, "C6", "100nF", "C", lcsc="C14663",
                mpn="CC0603KRX7R9BB104", pkg="C0603")
F_VCC(p1[0], p1[1]-10); F_GND(p2[0], p2[1])

# ---- 说明文字 ----
notes = [
    "1. 传感器 RP1~RP4: RP-C18.3-ST 薄膜压敏, 贴于装甲板背面4象限",
    "2. 半桥: 传感器->E+/A+, A-经10k配平电阻接GND; HX711统一3.3V供电",
    "3. U1引脚与hx711.c一致; CH4的SCK由PB10改为PB12, 腾出PB10/PB11作I2C2从机",
    "4. I2C地址=0x30+ID; J3~J5焊盘短接=1(PA0/PA1/PA2内部上拉), 无需额外芯片",
    "5. 主控经J1作I2C主机轮询4通道AD, 超阈值判受击; VCC=3.3V",
]
for k, s in enumerate(notes):
    T(60, -180 + k * -18, s, "#333333")

# ============================================================
# 组装文档
# ============================================================
xs, ys = [], []
for s in shapes:
    parts = s.split("~")
    try:
        if parts[0] in ("W",):
            pts = parts[1].split()
            xs += [float(pts[0]), float(pts[2])]; ys += [float(pts[1]), float(pts[3])]
        elif parts[0] in ("N", "J", "O"):
            xs.append(float(parts[1])); ys.append(float(parts[2]))
        elif parts[0] == "F":
            a = parts[6].split("~"); xs.append(float(a[0])); ys.append(float(a[1]))
        elif parts[0] == "T":
            xs.append(float(parts[2])); ys.append(float(parts[3]))
        elif parts[0] == "LIB":
            xs.append(float(parts[1])); ys.append(float(parts[2]))
    except (IndexError, ValueError):
        pass
bbox = {"x": min(xs) - 20, "y": min(ys) - 20, "width": max(xs) - min(xs) + 40,
        "height": max(ys) - min(ys) + 40}

doc_uuid = uuid.uuid4().hex
sheet_head = {
    "docType": "1", "editorVersion": "6.5.51", "newgId": True,
    "c_para": {"Prefix Start": "1"}, "c_spiceCmd": "null", "hasIdFlag": True,
    "uuid": doc_uuid, "x": "0", "y": "0", "portOfADImportHack": "",
    "importFlag": 0, "transformList": ""
}
data_str = {
    "head": sheet_head,
    "canvas": "CA~1000~1000~#FFFFFF~yes~#CCCCCC~5~1000~1000~line~5~pixel~5~0~0",
    "shape": shapes,
    "BBox": bbox,
    "colors": {}
}
doc = {
    "editorVersion": "6.5.51",
    "docType": "5",
    "title": "Armor_HX711_Node",
    "description": "装甲板受击检测节点 4xHX711+STM32F103C8T6",
    "colors": {},
    "schematics": [{
        "docType": "1",
        "title": "SCH_ArmorHX711",
        "description": "",
        "dataStr": data_str
    }]
}

out_dir = "/run/media/tianci/9058060F5805F52E/Trae/ZJBfankui/HX711_4ch_Scale"
# 容器版 (docType 5, 与官方示例结构一致)
with open(out_dir + "/armor_schematic_std.json", "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
# 单页版 (docType 1, 供"导入标准版单文件"使用)
single = dict(sheet_head)
single_doc = {"head": sheet_head, "canvas": data_str["canvas"], "shape": shapes,
              "BBox": bbox, "colors": {}}
with open(out_dir + "/armor_schematic_std_single.json", "w", encoding="utf-8") as f:
    json.dump(single_doc, f, ensure_ascii=False, indent=1)
print("shapes:", len(shapes), "| bbox:", bbox)
from collections import Counter
print(Counter(s.split("~")[0] for s in shapes))
print("saved docType5 + docType1")
