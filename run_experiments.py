"""Runs the real AnkiTube backend components over the corpus and records
timings (Exp.1), segment boundaries (Exp.2) and transcripts (Exp.3).

Usage (from backend/):  python ../experiments/run_experiments.py [limit]
Every video is appended to data/exp_results.jsonl; finished videos are skipped
so the run can be resumed.
"""
from __future__ import annotations

import json, os, shutil, sys, time, traceback
from pathlib import Path

EXP = Path(__file__).resolve().parent
SCRATCH = Path(os.environ["EXP_WORK"])
os.environ.update({"WORKDIR": str(SCRATCH / "work"), "OUTPUT_DIR": str(SCRATCH / "out"),
                   "YT_DLP_COOKIES_FROM_BROWSER": "", "YT_DLP_COOKIES_FILE": ""})
sys.path.insert(0, str(EXP.parent / "backend"))

import yt_dlp
from app.config import settings
from app.api.schemas import SegmentLength
from app.core.content_source import ContentKind
from app.llm.factory import get_llm_provider
from app.services.anki_builder import build_deck
from app.services.card_generation.factory import get_card_generator
from app.services.downloader import YouTubeDownloader
from app.services.segmenter import segment_transcript
from app.services.subtitles import srt_to_plain_transcript, transcript_srt_path
from app.services.transcriber import _get_model, transcribe_to_srt
from app.services.video_cutter import cut_segment
from app.api.schemas import GenerationMode, MediaMode
from app.utils.time_utils import seconds_to_timestamp

RESULTS = EXP / "data" / "exp_results.jsonl"
REFS = EXP / "data" / "refs"
REFS.mkdir(parents=True, exist_ok=True)


def fetch_captions(vid: str) -> dict:
    """Human ('manual') and YouTube-auto English captions as json3 (word-clean,
    no rolling-caption duplication). Not timed: used only as references."""
    out = {}
    for kind, opts in (("manual", {"writesubtitles": True}), ("auto", {"writeautomaticsub": True})):
        tmpl = str(REFS / f"{vid}.{kind}.%(ext)s")
        o = {"quiet": True, "no_warnings": True, "skip_download": True, "subtitleslangs": ["en"],
             "subtitlesformat": "json3", "outtmpl": tmpl, **opts}
        if Path(REFS / f"{vid}.{kind}.en.json3").exists():
            out[kind] = str(REFS / f"{vid}.{kind}.en.json3")
            continue
        for attempt in range(6):  # YouTube rate-limits the timedtext endpoint (429): back off and retry
            try:
                with yt_dlp.YoutubeDL(o) as y:
                    y.download(["https://www.youtube.com/watch?v=" + vid])
                break
            except Exception as exc:  # noqa: BLE001
                if "429" not in str(exc) or attempt == 5:
                    raise
                print(f"   429 on {kind} captions, waiting {60 * (attempt + 1)}s", flush=True)
                time.sleep(60 * (attempt + 1))
        time.sleep(5)
        out[kind] = str(REFS / f"{vid}.{kind}.en.json3")
    return out


def timed(fn, *a, **k):
    t = time.perf_counter()
    r = fn(*a, **k)
    return r, time.perf_counter() - t


def run_video(meta: dict, provider) -> dict:
    vid = meta["id"]
    rec = {"id": vid, "title": meta["title"], "channel": meta["channel"], "duration": meta["duration"]}
    settings.ensure_directories()
    shutil.rmtree(settings.workdir, ignore_errors=True)
    settings.ensure_directories()

    fetch_captions(vid)
    rec["refs"] = True

    # ---- stage 1: download (video + whatever subtitles the app picks) ----
    dl = YouTubeDownloader(settings.downloads_dir, preferred_lang="en")
    src, t_dl = timed(dl.download, "https://www.youtube.com/watch?v=" + vid)
    rec["t_download"] = t_dl
    rec["video_mb"] = round(src.video_path.stat().st_size / 1e6, 1)

    # ---- stage 2: local transcription (forced faster-whisper) ----
    srt = transcript_srt_path(src.video_path)
    _, t_tr = timed(transcribe_to_srt, src.video_path, srt, "en")
    rec["t_transcribe"] = t_tr
    shutil.copy(srt, REFS / f"{vid}.whisper.srt")
    transcript = srt_to_plain_transcript(srt)
    rec["n_whisper_cues"] = transcript.count("\n") + 1

    # ---- stage 3: segmentation (4 strategies + 2 extra fixed intervals) ----
    seg = {}
    for name, length in (("llm_auto", SegmentLength.AUTO), ("llm_short2", SegmentLength.SHORT),
                         ("llm_medium5", SegmentLength.MEDIUM)):
        try:
            chunks, t = timed(segment_transcript, provider, transcript, segment_length=length,
                              job_id="exp", provider_name="deepseek")
            seg[name] = {"t": t, "chunks": [(c.start_seconds, c.end_seconds) for c in chunks]}
        except Exception as exc:  # noqa: BLE001
            seg[name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    from app.services.segmentation.fixed_interval_segmenter import FixedIntervalSegmenter
    from app.api.schemas import GenerateRequest
    for iv in (10, 20, 60):
        req = GenerateRequest(url="https://www.youtube.com/watch?v=" + vid, fixed_interval_seconds=iv,
                              segmentation_strategy="fixed_interval", generation_mode="listening")
        chunks, t = timed(FixedIntervalSegmenter().segment, src, req, provider)
        seg[f"fixed_{iv}"] = {"t": t, "chunks": [(c.start_seconds, c.end_seconds) for c in chunks]}
    rec["seg"] = seg

    # ---- stage 4: packaging (cut clips + .apkg) for the AI-semantic strategy ----
    pk = {}
    for name in ("llm_auto", "fixed_20"):
        chunks = seg.get(name, {}).get("chunks")
        if not chunks:
            continue
        gen = get_card_generator(GenerationMode.LISTENING)
        from app.api.schemas import ContentChunk
        t0 = time.perf_counter()
        cards = []
        for i, (s, e) in enumerate(chunks, 1):
            ch = ContentChunk(title=f"p{i}", start=seconds_to_timestamp(s), end=seconds_to_timestamp(e))
            clip = settings.segments_dir / f"{name}-{i:03d}.mp4"
            sp = settings.segments_dir / f"{name}-{i:03d}.srt"
            cut_segment(src.video_path, clip, s, e)
            cards.append(gen.generate_card(ch, srt, sp, clip, provider, False, False, "es",
                                           media_mode=MediaMode.VIDEO))
        t_cut = time.perf_counter() - t0
        _, t_build = timed(build_deck, "exp", cards, settings.output_dir / f"{vid}-{name}.apkg",
                           gen.get_card_model(MediaMode.VIDEO))
        pk[name] = {"n_cards": len(cards), "t_cut_cards": t_cut, "t_build": t_build,
                    "apkg_mb": round((settings.output_dir / f"{vid}-{name}.apkg").stat().st_size / 1e6, 1)}
        for f in settings.segments_dir.glob(f"{name}-*"):
            f.unlink()
        (settings.output_dir / f"{vid}-{name}.apkg").unlink()
    rec["pack"] = pk
    rec["ok"] = True
    shutil.rmtree(settings.workdir, ignore_errors=True)
    return rec


def main() -> None:
    corpus = json.load(open(EXP / "data" / "corpus.json"))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(corpus)
    done = {r["id"] for r in map(json.loads, RESULTS.open()) if r.get("ok")} if RESULTS.exists() else set()
    provider = get_llm_provider()
    print("provider", provider.name, "| whisper", settings.whisper_model_size, settings.whisper_device,
          settings.whisper_compute_type, flush=True)
    _get_model(settings.whisper_device, settings.whisper_compute_type)  # load once, outside the timings
    for meta in corpus[:limit]:
        if meta["id"] in done:
            continue
        while True:  # never run (or time) a video while the connection is down
            try:
                import socket; socket.create_connection(("www.youtube.com", 443), timeout=5).close(); break
            except OSError:
                print("   sin conexion, esperando 30s", flush=True); time.sleep(30)
        print("==>", meta["id"], meta["title"][:50], flush=True)
        try:
            rec = run_video(meta, provider)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            rec = {"id": meta["id"], "ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
        with RESULTS.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print("   ", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in rec.items()
                      if k.startswith("t_") or k in ("ok", "error")}, flush=True)
        time.sleep(15)


if __name__ == "__main__":
    main()
