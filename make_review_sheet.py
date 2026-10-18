"""Builds the blind human-review sheet: a random sample of cards from each
segmentation method, shuffled, as a single self-contained HTML file plus a
private key (which method produced each card).

Card text is rebuilt from the saved cut points + the saved Whisper SRT with the
app's own helpers (split_srt_for_segment / read_segment_text), i.e. exactly how
a real card gets its text.
"""
from __future__ import annotations

import csv
import html
import json
import random
import sys
import tempfile
from pathlib import Path

EXP = Path(__file__).resolve().parent
sys.path.insert(0, str(EXP.parent / "backend"))
from app.services.srt_splitter import read_segment_text, split_srt_for_segment  # noqa: E402

EXCLUDE = {"t04SptVlGkQ", "QquPhtSOxas"}          # same exclusions as the experiments
METHODS = {"llm_auto": "IA semántica", "llm_short2": "IA límite 2", "llm_medium5": "IA límite 5",
           "fixed_20": "Intervalo fijo 20 s"}
PER_METHOD = 20
SEED = 42

rows = [json.loads(line) for line in (EXP / "data" / "exp_results.jsonl").open(encoding="utf-8")]
rows = [r for r in rows if r.get("ok") and r["id"] not in EXCLUDE]
rng = random.Random(SEED)

cards = []
tmp = Path(tempfile.mkdtemp())
for method in METHODS:
    pool = []
    for r in rows:
        seg = r["seg"].get(method, {})
        for i, (s, e) in enumerate(seg.get("chunks", [])):
            out = tmp / "seg.srt"
            split_srt_for_segment(EXP / "data" / "refs" / f"{r['id']}.whisper.srt", out, s, e)
            text = read_segment_text(out).strip()
            if text:
                pool.append({"method": method, "video": r["id"], "title": r["title"], "idx": i + 1,
                             "start": s, "end": e, "text": text})
    cards += rng.sample(pool, PER_METHOD)

rng.shuffle(cards)
for n, c in enumerate(cards, 1):
    c["n"] = n

(EXP / "review").mkdir(exist_ok=True)
with (EXP / "review" / "clave_privada.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tarjeta", "metodo", "video", "titulo_video", "segmento", "inicio_s", "fin_s", "duracion_s"])
    for c in cards:
        w.writerow([c["n"], c["method"], c["video"], c["title"], c["idx"], round(c["start"], 2),
                    round(c["end"], 2), round(c["end"] - c["start"], 1)])

blocks = []
for c in cards:
    blocks.append(f"""
<section class="card" id="c{c['n']}">
  <div class="head"><b>Tarjeta {c['n']}</b></div>
  <p class="text">{html.escape(c['text'])}</p>
  <div class="q"><span>¿Empieza y termina en una oración completa?</span>
    <label><input type="radio" name="a{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="a{c['n']}" value="0"> No</label></div>
  <div class="q"><span>¿Expresa una idea que se entiende sola?</span>
    <label><input type="radio" name="b{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="b{c['n']}" value="0"> No</label></div>
  <input class="note" name="n{c['n']}" placeholder="Comentario opcional (qué quedó cortado)">
</section>""")

page = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión de tarjetas</title>
<style>
:root{--bg:#f6f7f9;--fg:#1c2330;--card:#fff;--line:#d9dee7;--acc:#2f6bff;--dim:#667085}
@media (prefers-color-scheme:dark){:root{--bg:#12161d;--fg:#e8ecf3;--card:#1b212b;--line:#2c3544;--acc:#6b95ff;--dim:#98a2b3}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:46rem;margin:0 auto;padding:16px}
header{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);z-index:2}
.bar{height:6px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;width:0;background:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}
.head{display:flex;justify-content:space-between;color:var(--dim);font-size:.9rem}
.text{font-size:1.05rem;margin:8px 0 12px;white-space:pre-wrap}
.q{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;margin:6px 0}
.q span{flex:1 1 18rem}
label{cursor:pointer;padding:4px 10px;border:1px solid var(--line);border-radius:6px}
label:has(input:checked){background:var(--acc);color:#fff;border-color:var(--acc)}
input[type=radio]{margin-right:4px}
.note{width:100%;box-sizing:border-box;margin-top:8px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--fg)}
button{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:1rem;cursor:pointer}
small{color:var(--dim)}
</style></head><body><main>
<header><b>Revisión de tarjetas</b> · <span id="cnt">0</span> de TOTAL respondidas
<div class="bar"><i id="bar"></i></div></header>
<p>Lee cada tarjeta como si fuera una tarjeta de estudio: <b>solo el texto</b>, sin ver el video ni la duración.
Responde Sí o No en las dos preguntas. No sabes qué método generó cada una, a propósito.
Tus respuestas se guardan solas en este navegador; al terminar pulsa <i>Descargar respuestas</i>.</p>
BLOCKS
<p><button id="dl">Descargar respuestas (CSV)</button> <small id="msg"></small></p>
</main>
<script>
const TOTAL=TOTALN, KEY="revision_tarjetas_v1";
let st={}; try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
function refresh(){let n=0;for(let i=1;i<=TOTAL;i++) if(st["a"+i]!==undefined&&st["b"+i]!==undefined) n++;
 document.getElementById("cnt").textContent=n;document.getElementById("bar").style.width=(100*n/TOTAL)+"%"}
document.querySelectorAll("input").forEach(el=>{
 if(el.type==="radio"){ if(st[el.name]===el.value) el.checked=true;
   el.addEventListener("change",()=>{st[el.name]=el.value;save();refresh()}) }
 else { el.value=st[el.name]||""; el.addEventListener("input",()=>{st[el.name]=el.value;save()}) }});
refresh();
document.getElementById("dl").onclick=()=>{
 const q=s=>'"'+String(s||"").replace(/"/g,'""')+'"';
 let out="tarjeta,oracion_completa,idea_se_entiende_sola,comentario\\n",miss=0;
 for(let i=1;i<=TOTAL;i++){ if(st["a"+i]===undefined||st["b"+i]===undefined) miss++;
  out+=[i,st["a"+i]??"",st["b"+i]??"",q(st["n"+i])].join(",")+"\\n"}
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\\ufeff"+out],{type:"text/csv"}));
 a.download="respuestas_tarjetas.csv";a.click();
 document.getElementById("msg").textContent=miss?("Faltan "+miss+" tarjetas por responder."):"Listo, envíame el archivo."};
</script></body></html>"""
page = page.replace("BLOCKS", "\n".join(blocks)).replace("TOTALN", str(len(cards))).replace("TOTAL respondidas", f"{len(cards)} respondidas")
(EXP / "review" / "revision_tarjetas.html").write_text(page, encoding="utf-8")
print(len(cards), "tarjetas;", {m: sum(c['method'] == m for c in cards) for m in METHODS})
