#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HX711 4通道 RTT 可视化面板
用法：python3 rtt_dashboard.py  然后浏览器打开 http://localhost:8088
依赖：无（纯标准库）。需 openocd 的 rtt server 19021 口在跑。
"""
import json
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RTT_HOST, RTT_PORT = "127.0.0.1", 19021
HTTP_PORT = 8088

CH_COLORS = ["#fcee0a", "#00f0ff", "#ff2d95", "#57ff5e"]
CH_NAMES = ["CH1", "CH2", "CH3", "CH4"]

state = {
    "raw": [None] * 4,
    "net": [None] * 4,
    "off": [True] * 4,
    "connected": False,
    "rate": 0,
}
_line_cnt = 0

CH_RE = re.compile(r"CH([1-4]):(OFF|-?\d+)/(-?\d+)")


def parse_line(line):
    global _line_cnt
    hits = CH_RE.findall(line)
    if not hits:
        return
    _line_cnt += 1
    with_state = False
    for ch_s, val, net in hits:
        ch = int(ch_s) - 1
        if val == "OFF":
            state["off"][ch] = True
        else:
            state["off"][ch] = False
            state["raw"][ch] = int(val)
            state["net"][ch] = int(net)
            with_state = True
    if with_state:
        state["connected"] = True


def rate_counter():
    global _line_cnt
    while True:
        time.sleep(1.0)
        state["rate"] = _line_cnt
        _line_cnt = 0


def rtt_reader():
    while True:
        try:
            s = socket.create_connection((RTT_HOST, RTT_PORT), timeout=3)
            s.settimeout(None)
            buf = b""
            while True:
                d = s.recv(4096)
                if not d:
                    break
                buf += d
                while b"\n" in buf:
                    raw_line, buf = buf.split(b"\n", 1)
                    parse_line(raw_line.decode("ascii", "ignore"))
        except OSError:
            state["connected"] = False
        time.sleep(2)


PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>ARMOR SCALE // 4CH HX711</title>
<style>
  :root { --bg:#0a0a12; --panel:#10111c; --line:#232438; --yellow:#fcee0a;
          --cyan:#00f0ff; --pink:#ff2d95; --green:#57ff5e; --dim:#6a6d8a; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:#d7dae8; font-family:'Segoe UI',Consolas,monospace;
         min-height:100vh; padding:18px; }
  body::after { content:''; position:fixed; inset:0; pointer-events:none;
    background:repeating-linear-gradient(0deg,transparent 0 2px,rgba(0,0,0,.12) 2px 4px); }
  h1 { font-size:15px; letter-spacing:4px; color:var(--yellow); margin-bottom:4px;
       text-shadow:0 0 8px rgba(252,238,10,.5); }
  .sub { font-size:11px; color:var(--dim); letter-spacing:2px; margin-bottom:14px; }
  .sub b { color:var(--cyan); }
  .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:14px; }
  .card { background:var(--panel); border:1px solid var(--line); padding:12px 14px;
          position:relative; clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,10px 100%,0 calc(100% - 10px)); }
  .card .name { font-size:12px; letter-spacing:3px; color:var(--dim); display:flex; justify-content:space-between; }
  .card .dot { width:8px; height:8px; border-radius:50%; background:#333; margin-top:3px; }
  .card .dot.on { background:var(--green); box-shadow:0 0 6px var(--green); }
  .card .val { font-size:34px; font-weight:700; margin:6px 0 2px; font-variant-numeric:tabular-nums; }
  .card .raw { font-size:10px; color:var(--dim); font-variant-numeric:tabular-nums; }
  .barwrap { height:6px; background:#1a1b2b; margin-top:8px; }
  .bar { height:100%; width:0%; transition:width .08s linear; }
  .panel { background:var(--panel); border:1px solid var(--line); padding:12px;
           clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,10px 100%,0 calc(100% - 10px)); }
  .legend { display:flex; gap:18px; font-size:11px; color:var(--dim); letter-spacing:2px; margin-bottom:8px; }
  .legend span::before { content:''; display:inline-block; width:14px; height:3px; margin-right:6px; vertical-align:middle; }
  .l0 span::before{background:var(--yellow)} .l1 span::before{background:var(--cyan)}
  .l2 span::before{background:var(--pink)} .l3 span::before{background:var(--green)}
  canvas { width:100%; height:300px; display:block; }
  .note { font-size:10px; color:var(--dim); margin-top:10px; letter-spacing:1px; }
</style>
</head>
<body>
<h1>ARMOR SCALE // 4CH HX711</h1>
<div class="sub">RTT <b id="st">CONNECTING...</b> &nbsp;|&nbsp; RATE <b id="rate">0</b> Hz &nbsp;|&nbsp; 单位: raw counts（未标定）</div>
<div class="cards">
""" + "".join(f"""
  <div class="card">
    <div class="name" style="color:{CH_COLORS[i]}">{CH_NAMES[i]}<span class="dot" id="dot{i}"></span></div>
    <div class="val" style="color:{CH_COLORS[i]}" id="val{i}">--</div>
    <div class="raw" id="raw{i}">RAW --</div>
    <div class="barwrap"><div class="bar" id="bar{i}" style="background:{CH_COLORS[i]}"></div></div>
  </div>""" for i in range(4)) + """
</div>
<div class="panel">
  <div class="legend">""" + "".join(f'<span class="l{i}">{CH_NAMES[i]} NET</span>' for i in range(4)) + """</div>
  <canvas id="chart"></canvas>
  <div class="note">净值 = 原始值 - 上电零点（装甲板空载 TARE）。放已知重量后可标定成 kg。</div>
</div>
<script>
const N = 600;
const hist = [[],[],[],[]];
const el = i => document.getElementById(i);
function fmt(v){ return v===null ? '--' : v.toLocaleString('en-US'); }
const es = new EventSource('/stream');
es.onopen = () => el('st').textContent = 'LINK OK';
es.onerror = () => el('st').textContent = 'LINK DOWN';
es.onmessage = e => {
  const d = JSON.parse(e.data);
  el('rate').textContent = d.rate;
  el('st').textContent = d.connected ? 'LINK OK' : 'RTT WAITING...';
  for (let i=0;i<4;i++){
    el('dot'+i).className = 'dot' + (d.off[i] ? '' : ' on');
    if (d.off[i] || d.net[i]===null){ el('val'+i).textContent='OFF'; el('raw'+i).textContent='RAW --'; }
    else {
      el('val'+i).textContent = fmt(d.net[i]);
      el('raw'+i).textContent = 'RAW ' + fmt(d.raw[i]);
      hist[i].push(d.net[i]); if (hist[i].length>N) hist[i].shift();
    }
  }
  draw();
};
const cv = el('chart'), ctx = cv.getContext('2d');
function draw(){
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width!==W) cv.width=W; if (cv.height!==H) cv.height=H;
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='#1c1d30'; ctx.lineWidth=1; ctx.font='10px monospace'; ctx.fillStyle='#6a6d8a';
  for (let g=0; g<=4; g++){ const y=H*g/4; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }
  let lo=Infinity, hi=-Infinity, len=0;
  for (const h of hist){ len=Math.max(len,h.length); for (const v of h){ if(v<lo)lo=v; if(v>hi)hi=v; } }
  if (!len || lo===Infinity) return;
  if (hi-lo < 100){ const m=(hi+lo)/2; lo=m-50; hi=m+50; }
  const pad=(hi-lo)*0.08; lo-=pad; hi+=pad;
  ctx.fillText(hi.toLocaleString(), 4, 12);
  ctx.fillText(lo.toLocaleString(), 4, H-4);
  for (let i=0;i<4;i++){
    const h=hist[i]; if (!h.length) continue;
    ctx.strokeStyle=CH_COLORS[i]; ctx.lineWidth=1.5; ctx.beginPath();
    const step=Math.max(1, Math.floor(h.length/(W/2)));
    for (let k=0;k<h.length;k+=step){
      const x=W-((h.length-1-k)/(N-1))*W, y=H-(h[k]-lo)/(hi-lo)*H;
      k===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }
    ctx.stroke();
  }
}
window.addEventListener('resize', draw);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    snap = json.dumps({
                        "raw": state["raw"], "net": state["net"],
                        "off": state["off"], "connected": state["connected"],
                        "rate": state["rate"],
                    })
                    self.wfile.write(f"data: {snap}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    threading.Thread(target=rtt_reader, daemon=True).start()
    threading.Thread(target=rate_counter, daemon=True).start()
    print(f"面板: http://localhost:{HTTP_PORT}  (RTT {RTT_HOST}:{RTT_PORT})")
    ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler).serve_forever()
