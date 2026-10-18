"""Blind review sheet v2 WITH AUDIO: same 80 sampled cards as v1 (same seed), new
shuffle/numbering. For every card the audio clip is cut exactly like the app
does (extract_audio_segment: AAC re-encode, frame-accurate -ss/-t) from a fresh
download of the video, then embedded in a single HTML file.

Usage (from backend/):  EXP_WORK=<scratch dir> python -X utf8 ../experiments/make_review_audio.py
Resumable: clips already cut are reused.
"""
from __future__ import annotations

import base64
import csv
import html
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent
SCR = Path(os.environ["EXP_WORK"])
os.environ.update({"WORKDIR": str(SCR / "work3"), "OUTPUT_DIR": str(SCR / "out3"),
                   "YT_DLP_COOKIES_FROM_BROWSER": "", "YT_DLP_COOKIES_FILE": ""})
sys.path.insert(0, str(EXP.parent / "backend"))
from app.config import settings  # noqa: E402
from app.services.downloader import YouTubeDownloader  # noqa: E402
from app.services.ffmpeg_locator import resolve_ffmpeg_path  # noqa: E402
from app.services.srt_splitter import read_segment_text, split_srt_for_segment  # noqa: E402
from app.services.video_cutter import extract_audio_segment  # noqa: E402

EXCLUDE = {"t04SptVlGkQ", "QquPhtSOxas"}
METHODS = ["llm_auto", "llm_short2", "llm_medium5", "fixed_20"]
PER_METHOD, SEED = 20, 42
CLIPS = SCR / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)

# ---- same sample as v1 (identical code + seed => identical 80 cards) ----
rows = [json.loads(line) for line in (EXP / "data" / "exp_results.jsonl").open(encoding="utf-8")]
rows = [r for r in rows if r.get("ok") and r["id"] not in EXCLUDE]
rng = random.Random(SEED)
tmp = Path(tempfile.mkdtemp())
cards = []
for method in METHODS:
    pool = []
    for r in rows:
        for i, (s, e) in enumerate(r["seg"].get(method, {}).get("chunks", [])):
            out = tmp / "seg.srt"
            split_srt_for_segment(EXP / "data" / "refs" / f"{r['id']}.whisper.srt", out, s, e)
            text = read_segment_text(out).strip()
            if text:
                pool.append({"method": method, "video": r["id"], "title": r["title"], "idx": i + 1,
                             "start": s, "end": e, "text": text})
    cards += rng.sample(pool, PER_METHOD)
rng.shuffle(cards)                                   # = v1 order (used only to key the clips)
for n, c in enumerate(cards, 1):
    c["old"] = n
    c["clip"] = CLIPS / f"{c['video']}_{c['method']}_{c['idx']:03d}.m4a"

# ---- cut the audio clips ----
ffmpeg = resolve_ffmpeg_path()
by_video: dict[str, list] = {}
for c in cards:
    if not c["clip"].exists():
        by_video.setdefault(c["video"], []).append(c)
print(len(cards), "tarjetas;", len(by_video), "videos por descargar", flush=True)
settings.ensure_directories()
for vid, items in by_video.items():
    for attempt in range(4):
        try:
            shutil.rmtree(settings.workdir, ignore_errors=True)
            settings.ensure_directories()
            src = YouTubeDownloader(settings.downloads_dir, "en").download("https://www.youtube.com/watch?v=" + vid)
            break
        except Exception as exc:  # noqa: BLE001
            print("  reintento", vid, str(exc)[:80], flush=True)
            time.sleep(30 * (attempt + 1))
    else:
        raise SystemExit(f"no se pudo descargar {vid}")
    for c in items:
        raw = settings.segments_dir / "raw.m4a"
        extract_audio_segment(src.video_path, raw, c["start"], c["end"])
        # smaller file for embedding; boundaries are unchanged
        subprocess.run([ffmpeg, "-y", "-i", str(raw), "-ac", "1", "-b:a", "48k", str(c["clip"])],
                       check=True, capture_output=True)
    print("  ok", vid, len(items), "clips", flush=True)
    time.sleep(3)
shutil.rmtree(settings.workdir, ignore_errors=True)

# ---- new blind order ----
rng2 = random.Random(SEED + 1)
rng2.shuffle(cards)
for n, c in enumerate(cards, 1):
    c["n"] = n
(EXP / "review").mkdir(exist_ok=True)
with (EXP / "review" / "clave_privada_audio.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tarjeta", "metodo", "video", "titulo_video", "segmento", "inicio_s", "fin_s", "duracion_s", "tarjeta_v1"])
    for c in cards:
        w.writerow([c["n"], c["method"], c["video"], c["title"], c["idx"], round(c["start"], 2),
                    round(c["end"], 2), round(c["end"] - c["start"], 1), c["old"]])

blocks = []
for c in cards:
    b64 = base64.b64encode(c["clip"].read_bytes()).decode()
    blocks.append(f"""
<section class="card" id="c{c['n']}">
  <div class="head"><b>Tarjeta {c['n']}</b></div>
  <audio controls preload="none" src="data:audio/mp4;base64,{b64}"></audio>
  <div class="q"><span>¿El audio <b>empieza</b> limpio (no a mitad de palabra ni de frase)?</span>
    <label><input type="radio" name="a{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="a{c['n']}" value="0"> No</label></div>
  <div class="q"><span>¿El audio <b>termina</b> limpio (no se corta a mitad de palabra ni de frase)?</span>
    <label><input type="radio" name="b{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="b{c['n']}" value="0"> No</label></div>
  <div class="q"><span>¿Es una idea que se entiende sola, completa?</span>
    <label><input type="radio" name="d{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="d{c['n']}" value="0"> No</label></div>
  <div class="txt"><small>Texto de la tarjeta (léelo después de contestar las 3 primeras preguntas):</small>
    <p class="text">{html.escape(c['text'])}</p></div>
  <div class="q"><span>¿El texto <b>coincide</b> con lo que oíste, sin que le sobren ni le falten palabras en el inicio o el final?</span>
    <label><input type="radio" name="e{c['n']}" value="1"> Sí</label>
    <label><input type="radio" name="e{c['n']}" value="0"> No, le sobra</label>
    <label><input type="radio" name="e{c['n']}" value="2"> No, le falta</label></div>
  <input class="note" name="n{c['n']}" placeholder="Comentario opcional">
</section>""")

page = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión de tarjetas con audio</title>
<style>
:root{--bg:#f6f7f9;--fg:#1c2330;--card:#fff;--line:#d9dee7;--acc:#2f6bff;--dim:#667085}
@media (prefers-color-scheme:dark){:root{--bg:#12161d;--fg:#e8ecf3;--card:#1b212b;--line:#2c3544;--acc:#6b95ff;--dim:#98a2b3}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:46rem;margin:0 auto;padding:16px}
header{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);z-index:2}
.bar{height:6px;background:var(--line);border-radius:4px;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;width:0;background:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}
.head{color:var(--dim);font-size:.9rem;margin-bottom:6px}
audio{width:100%;margin:4px 0 8px}
.text{margin:8px 0;white-space:pre-wrap}
.txt{margin:8px 0;padding:8px 12px;border-left:3px solid var(--line)}
.q{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;margin:6px 0}
.q span{flex:1 1 18rem}
label{cursor:pointer;padding:4px 10px;border:1px solid var(--line);border-radius:6px}
label:has(input:checked){background:var(--acc);color:#fff;border-color:var(--acc)}
input[type=radio]{margin-right:4px}
.note{width:100%;box-sizing:border-box;margin-top:8px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--fg)}
button{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:1rem;cursor:pointer}
small{color:var(--dim)}
</style></head><body><main>
<header><b>Revisión con audio</b> · <span id="cnt">0</span> de TOTALN respondidas
<div class="bar"><i id="bar"></i></div></header>
<p>Escucha cada clip completo, tal como lo oiría un estudiante, y responde las tres primeras preguntas solo con lo que oyes.
Presta atención al <b>primer</b> y al <b>último</b> segundo: ¿se oye una palabra o frase cortada?
Después lee el texto de la tarjeta y contesta la cuarta: ¿dice más o menos de lo que se oye? No sabes qué método generó cada clip, a propósito.
Tus respuestas se guardan solas en este navegador; al terminar pulsa <i>Descargar respuestas</i>.</p>
BLOCKS
<p><button id="dl">Descargar respuestas (CSV)</button> <small id="msg"></small></p>
</main>
<script>
const TOTAL=TOTALN, KEY="revision_audio_v1";
let st={}; try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
function refresh(){let n=0;for(let i=1;i<=TOTAL;i++) if(["a","b","d","e"].every(p=>st[p+i]!==undefined)) n++;
 document.getElementById("cnt").textContent=n;document.getElementById("bar").style.width=(100*n/TOTAL)+"%"}
document.querySelectorAll("input").forEach(el=>{
 if(el.type==="radio"){ if(st[el.name]===el.value) el.checked=true;
   el.addEventListener("change",()=>{st[el.name]=el.value;save();refresh()}) }
 else { el.value=st[el.name]||""; el.addEventListener("input",()=>{st[el.name]=el.value;save()}) }});
refresh();
document.getElementById("dl").onclick=()=>{
 const q=s=>'"'+String(s||"").replace(/"/g,'""')+'"';
 let out="tarjeta,empieza_limpio,termina_limpio,idea_completa,texto_coincide,comentario\\n",miss=0;
 for(let i=1;i<=TOTAL;i++){ if(["a","b","d","e"].some(p=>st[p+i]===undefined)) miss++;
  out+=[i,st["a"+i]??"",st["b"+i]??"",st["d"+i]??"",st["e"+i]??"",q(st["n"+i])].join(",")+"\\n"}
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["\\ufeff"+out],{type:"text/csv"}));
 a.download="respuestas_audio.csv";a.click();
 document.getElementById("msg").textContent=miss?("Faltan "+miss+" tarjetas por responder."):"Listo, envíame el archivo."};
</script></body></html>"""
page = page.replace("BLOCKS", "\n".join(blocks)).replace("TOTALN", str(len(cards)))
out_html = EXP / "review" / "revision_con_audio.html"
out_html.write_text(page, encoding="utf-8")
print("listo:", out_html, round(out_html.stat().st_size / 1e6, 1), "MB", flush=True)
