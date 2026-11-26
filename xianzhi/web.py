"""Web 入口:零依赖 http.server,单页 + JSON API。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import agent, llm
from . import db as dbmod

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>闲置 · 二手定价助手</title>
<style>
  :root{--bg:#f6f6f3;--card:#fff;--ink:#242420;--muted:#77776e;--accent:#4a6b48;--soft:#e6efe4;
        --line:#e3e3dc;--amber:#b98326;--red:#b0412f;--radius:16px}
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
  .wrap{max-width:940px;margin:0 auto;padding:32px 20px 80px}
  h1{font-size:26px;margin:0 0 4px} header p{color:var(--muted);margin:0 0 22px}
  .badge{display:inline-block;font-size:12px;padding:3px 10px;border-radius:999px;background:var(--soft);color:var(--accent);margin-left:8px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;margin-bottom:18px;box-shadow:0 1px 2px rgba(36,36,32,.04)}
  label{display:block;font-size:13px;color:var(--muted);margin:0 0 6px}
  textarea,input{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font-size:14px;font-family:inherit;background:#fff}
  textarea{line-height:1.7}
  textarea:focus,input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--soft)}
  .row{display:flex;gap:12px;flex-wrap:wrap}.row>div{flex:1;min-width:180px}
  button{background:var(--accent);color:#fff;border:none;padding:12px 22px;border-radius:12px;font-size:15px;cursor:pointer}
  button:hover{filter:brightness(1.1)}
  .hint{color:var(--muted);font-size:12px;margin-top:8px}
  .spin{display:inline-block;width:16px;height:16px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:sp .7s linear infinite}
  @keyframes sp{to{transform:rotate(360deg)}}
  .result{display:none}.result.show{display:block}
  h3{font-size:15px;color:var(--muted);margin:20px 0 8px}
  .price{font-size:30px;font-weight:700;color:var(--accent)}
  .box{background:#fafaf7;border-radius:10px;padding:12px 14px;margin:8px 0;font-size:14px;white-space:pre-wrap;line-height:1.7}
  .item{border-left:3px solid var(--accent);padding:4px 0 4px 12px;margin:8px 0;font-size:14px}
  .bad{color:var(--red)}.ok{color:var(--accent)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:600}
  ul{margin:6px 0 0 18px;padding:0}li{margin:6px 0;font-size:14px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>闲置 · 二手定价助手<span class="badge" id="badge">…</span></h1>
    <p>写清楚是什么、几成新、买了多久、有什么瑕疵,给你价格区间、平台到手价和一整套挂牌文字。</p>
  </header>
  <div class="card">
    <label>商品描述</label>
    <textarea id="text" rows="6" placeholder="iPhone 13 128G,95新,2023年买的,电池健康 82%,屏幕有细微划痕,无盒"></textarea>
    <div class="row" style="margin-top:12px">
      <div><label>原价(元)</label><input id="original" placeholder="例:5999"></div>
      <div><label>最低接受价(可选,留空按公式)</label><input id="floor" placeholder="例:1800"></div>
    </div>
    <div style="margin-top:16px"><button id="btn">算价并生成文案</button></div>
    <div class="hint">折旧、成色、瑕疵、平台费率、砍价话术全在本地;模型只写挂牌建议,金额不会被模型改写。</div>
  </div>
  <div class="result" id="res"></div>
</div>
<script>
const $=s=>document.querySelector(s);
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function load(btn,on){btn.disabled=on;if(on){btn.dataset.label=btn.dataset.label||btn.textContent.trim();btn.innerHTML='<span class="spin"></span>';}else{btn.innerHTML=btn.dataset.label||btn.textContent;}}
$('#btn').onclick=async()=>{
  const el=$('#res');el.classList.remove('show');load($('#btn'),true);
  try{
    const p=await fetch('/api/quote',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:$('#text').value,original:$('#original').value,floor:$('#floor').value})});
    const r=await p.json(); if(r.error) throw new Error(r.error);
    let h='<div class="card"><div class="hint">'+(r.mode==='model'?'模型已连接':'离线模式')+(r.saved_id?' · 已入库 #'+r.saved_id:'')+'</div>';
    h+='<p style="font-size:16px;line-height:1.7">'+esc(r.verdict)+'</p>';
    if(r.price){
      h+='<div class="price">'+r.price.suggested+' 元</div><div class="hint">区间 '+r.price.low+'–'+r.price.high+' · 底价 '+r.price.floor_price+(r.price.floor_from_user?'(你填的)':'')+' · 残值基数 '+r.price.base+'</div>';
      h+='<div class="hint" style="margin-top:8px">'+esc(r.price.formula)+'</div>';
      h+='<h3>平台到手</h3><table><tr><th>平台</th><th>费率</th><th>到手</th><th>说明</th></tr>';
      r.platforms.forEach(x=>{h+='<tr><td>'+esc(x.name)+'</td><td>'+(x.fee*100).toFixed(1)+'%'+(x.discount?' · 折价 '+(x.discount*100).toFixed(0)+'%':'')+'</td><td>'+x.net+' 元</td><td class="hint">'+esc(x.days)+' · '+esc(x.extra)+'</td></tr>';});
      h+='</table>';
    }
    if(r.listing){h+='<h3>标题</h3><div class="box">'+esc(r.listing.title)+'</div>';
      h+='<h3>正文</h3><div class="box">'+esc(r.listing.body)+'</div>';
      h+='<h3>标签</h3><div class="hint">'+esc(r.listing.tags.map(t=>'#'+t).join(' '))+'</div>';}
    if(r.bargain.length){h+='<h3>砍价三档</h3>';
      r.bargain.forEach(b=>{h+='<div class="item"><b>'+esc(b.tier)+' -'+b.pct+'%</b> 对方出 '+b.offer+' → '+esc(b.reply)+'</div>';});}
    if(r.banned.length){h+='<h3>违禁/导流词</h3>';r.banned.forEach(w=>{h+='<div class="item bad"><b>'+esc(w.word)+'</b> ['+esc(w.type)+'] '+esc(w.why)+'<div class="hint">改:'+esc(w.fix)+'</div></div>';});}
    h+='<h3>挂牌体检</h3>';
    r.checklist.forEach(c=>{h+='<div class="'+(c.ok?'ok':'bad')+'">'+(c.ok?'✅':'❌')+' '+esc(c.item)+' —— '+esc(c.how)+'</div>';});
    if(r.tips.length){h+='<h3>挂牌建议</h3><ul>';r.tips.forEach(x=>h+='<li>'+esc(x)+'</li>');h+='</ul>';}
    if(r.risks.length){h+='<h3>交易风险</h3><ul>';r.risks.forEach(x=>h+='<li class="bad">'+esc(x)+'</li>');h+='</ul>';}
    if(r.buyer_questions.length){h+='<h3>买家会问</h3><ul>';r.buyer_questions.forEach(x=>h+='<li>'+esc(x)+'</li>');h+='</ul>';}
    h+='</div>'; el.innerHTML=h;
  }catch(e){el.innerHTML='<div class="card" style="color:#b0412f">请求失败:'+esc(e.message)+'</div>';}
  el.classList.add('show');load($('#btn'),false);
};
fetch('/api/status').then(r=>r.json()).then(s=>{const b=$('#badge');
  if(s.mock){b.textContent='离线模式';b.style.background='#fee2e2';b.style.color='#b0412f';}
  else{b.textContent=s.model||'模型已连接';b.style.background='#dcfce7';b.style.color='#4a6b48';}
}).catch(()=>{});
</script>
</body></html>
"""


def _handler(db, cfg, force_mock):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, ctype, status=200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _read(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            return json.loads(text) if text else {}

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/status":
                mock = force_mock or not cfg.get("api_key")
                self._json({"mock": mock, "model": None if mock else cfg.get("model")})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/quote":
                self._json({"error": "not found"}, 404)
                return
            try:
                body = self._read()
                original = body.get("original")
                original = float(original) if str(original).strip() not in ("", "None", "null") else None
                floor = body.get("floor")
                floor = float(floor) if str(floor).strip() not in ("", "None", "null") else None
                r = agent.quote(body.get("text", ""), original=original, config=cfg,
                                db=db, force_mock=force_mock, save=True, floor=floor)
                self._json(r)
            except llm.LLMError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 500)

        def log_message(self, *args):
            pass

    return Handler


def serve(host="127.0.0.1", port=8000, db_path=None, force_mock=False):
    db = dbmod.Database(db_path)
    cfg = llm.default_config()
    httpd = ThreadingHTTPServer((host, port), _handler(db, cfg, force_mock))
    mode = "离线模式(未配置 key)" if (force_mock or not cfg.get("api_key")) else "模型:%s" % cfg.get("model")
    print("🏷  闲置已启动:http://%s:%s  [%s]" % (host, port, mode))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
