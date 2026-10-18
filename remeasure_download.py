"""Second, independent timing of stage 1 (download) on a stable connection."""
import json, os, shutil, sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parent
SCR = Path(os.environ["EXP_WORK"])
os.environ.update({"WORKDIR": str(SCR / "work2"), "OUTPUT_DIR": str(SCR / "out2"),
                   "YT_DLP_COOKIES_FROM_BROWSER": "", "YT_DLP_COOKIES_FILE": ""})
sys.path.insert(0, str(EXP.parent / "backend"))
from app.config import settings
from app.services.downloader import YouTubeDownloader
out = EXP / "data" / "download_remeasure.jsonl"
done = {json.loads(l)["id"] for l in out.open()} if out.exists() else set()
ids = [json.loads(l)["id"] for l in (EXP / "data" / "exp_results.jsonl").open() if json.loads(l).get("ok")]
for vid in ids:
    if vid in done: continue
    shutil.rmtree(settings.workdir, ignore_errors=True); settings.ensure_directories()
    t = time.perf_counter()
    try:
        r = YouTubeDownloader(settings.downloads_dir, "en").download("https://www.youtube.com/watch?v=" + vid)
        rec = {"id": vid, "t": time.perf_counter() - t, "mb": round(r.video_path.stat().st_size / 1e6, 1), "ok": True}
    except Exception as e:
        rec = {"id": vid, "ok": False, "error": str(e)[:150]}
    with out.open("a") as f: f.write(json.dumps(rec) + "\n")
    print(rec, flush=True); time.sleep(4)
shutil.rmtree(settings.workdir, ignore_errors=True)
