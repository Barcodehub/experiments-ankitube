"""Turns data/exp_results.jsonl + data/refs/* into the tables of the report."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
from scipy import stats

D = Path(__file__).parent / "data"
REFS = D / "refs"
rows = [json.loads(line) for line in (D / "exp_results.jsonl").open()]
import os
EXCL = set(filter(None, os.environ.get("EXCLUDE", "").split(",")))   # post-hoc exclusions (invalid reference)
SUFFIX = os.environ.get("SUFFIX", "")
ok_all = [r for r in rows if r.get("ok")]
ok = [r for r in ok_all if r["id"] not in EXCL]
OUT: dict = {"n_ok": len(ok), "n_failed": len(rows) - len(ok),
             "failed": [(r["id"], r.get("error")) for r in rows if not r.get("ok")]}


def ms(x):
    x = list(x)
    return {"mean": float(np.mean(x)), "sd": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
            "median": float(np.median(x)), "min": float(min(x)), "max": float(max(x)), "n": len(x)}


def boot_ci(x, f=np.mean, n=5000, seed=1):
    x = np.asarray(list(x))
    rng = np.random.default_rng(seed)
    b = [f(rng.choice(x, len(x))) for _ in range(n)]
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


# ------------------------------------------------------------------ Exp 1
e1: dict = {}
dur = np.array([r["duration"] for r in ok])
OUT["corpus"] = {"videos": len(ok), "total_min": float(dur.sum() / 60), "dur": ms(dur / 60),
                 "mb": ms([r["video_mb"] for r in ok])}


def has(r, k):
    return "t" in r["seg"][k]


stage = {
    "download": [r["t_download"] for r in ok],
    "transcribe": [r["t_transcribe"] for r in ok],
    "seg_llm_auto": [r["seg"]["llm_auto"]["t"] for r in ok if has(r, "llm_auto")],
    "seg_llm_short2": [r["seg"]["llm_short2"]["t"] for r in ok if has(r, "llm_short2")],
    "seg_llm_medium5": [r["seg"]["llm_medium5"]["t"] for r in ok if has(r, "llm_medium5")],
    "seg_fixed20": [r["seg"]["fixed_20"]["t"] for r in ok],
    "pack_cut_llm_auto": [r["pack"]["llm_auto"]["t_cut_cards"] for r in ok if "llm_auto" in r["pack"]],
    "pack_build_llm_auto": [r["pack"]["llm_auto"]["t_build"] for r in ok if "llm_auto" in r["pack"]],
    "pack_cut_fixed20": [r["pack"]["fixed_20"]["t_cut_cards"] for r in ok],
    "pack_build_fixed20": [r["pack"]["fixed_20"]["t_build"] for r in ok],
}
rem = {x["id"]: x for x in map(json.loads, (D / "download_remeasure.jsonl").open(encoding="utf-8")) if x.get("ok")}
stage["download_run2"] = [rem[r["id"]]["t"] for r in ok if r["id"] in rem]
stage["download_mean_of_2"] = [(r["t_download"] + rem[r["id"]]["t"]) / 2 for r in ok if r["id"] in rem]
e1["download_pairs"] = [(r["id"], r["t_download"], rem[r["id"]]["t"], r["video_mb"]) for r in ok if r["id"] in rem]
e1["download_run1_run2_r"] = float(np.corrcoef([p[1] for p in e1["download_pairs"]], [p[2] for p in e1["download_pairs"]])[0, 1])
e1["download_vs_mb_r"] = float(np.corrcoef([p[3] for p in e1["download_pairs"]], [p[2] for p in e1["download_pairs"]])[0, 1])
e1["stages"] = {k: ms(v) for k, v in stage.items()}
tot_ai, tot_fx, rtf_ai, rtf_fx = [], [], [], []
share = {"download": [], "transcribe": [], "segment": [], "package": []}
for r in ok:
    if not has(r, "llm_auto") or "llm_auto" not in r["pack"]:
        continue
    pk = r["pack"]["llm_auto"]
    s = r["seg"]["llm_auto"]["t"]
    dl = (r["t_download"] + rem[r["id"]]["t"]) / 2 if r["id"] in rem else r["t_download"]
    t = dl + r["t_transcribe"] + s + pk["t_cut_cards"] + pk["t_build"]
    tot_ai.append(t)
    rtf_ai.append(t / r["duration"])
    for k, v in (("download", dl), ("transcribe", r["t_transcribe"]), ("segment", s),
                 ("package", pk["t_cut_cards"] + pk["t_build"])):
        share[k].append(v / t)
    pf = r["pack"]["fixed_20"]
    tf = dl + r["t_transcribe"] + pf["t_cut_cards"] + pf["t_build"]
    tot_fx.append(tf)
    rtf_fx.append(tf / r["duration"])
e1["total_ai"] = ms(tot_ai)
e1["total_fixed"] = ms(tot_fx)
e1["rtf_ai"] = ms(rtf_ai)
e1["rtf_fixed"] = ms(rtf_fx)
e1["total_ai_ci"] = boot_ci(tot_ai)
e1["share_pct"] = {k: float(np.mean(v) * 100) for k, v in share.items()}
e1["whisper_rtf"] = ms([r["t_transcribe"] / r["duration"] for r in ok])
e1["transcribe_vs_duration_r"] = float(np.corrcoef(dur, [r["t_transcribe"] for r in ok])[0, 1])
e1["n_cards"] = {"llm_auto": ms([r["pack"]["llm_auto"]["n_cards"] for r in ok if "llm_auto" in r["pack"]]),
                 "fixed_20": ms([r["pack"]["fixed_20"]["n_cards"] for r in ok])}
e1["apkg_mb"] = {"llm_auto": ms([r["pack"]["llm_auto"]["apkg_mb"] for r in ok if "llm_auto" in r["pack"]]),
                 "fixed_20": ms([r["pack"]["fixed_20"]["apkg_mb"] for r in ok])}
e1["cut_per_card"] = ms([r["pack"]["llm_auto"]["t_cut_cards"] / r["pack"]["llm_auto"]["n_cards"]
                         for r in ok if "llm_auto" in r["pack"]])
e1["seg_errors"] = {k: sum(1 for r in ok if "error" in r["seg"][k]) for k in ("llm_auto", "llm_short2", "llm_medium5")}
OUT["exp1"] = e1


# ------------------------------------------------------------------ reference parsing
def load_json3(path):
    cues = []
    for e in json.load(open(path))["events"]:
        if "segs" not in e:
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).replace("\n", " ")
        if text.strip():
            cues.append((e["tStartMs"] / 1000, (e["tStartMs"] + e.get("dDurationMs", 0)) / 1000, text.strip()))
    return cues


def _secs(t):
    return sum(float(x.replace(",", ".")) * m for x, m in zip(t.split(":"), (3600, 60, 1)))


def read_srt(path):
    out = []
    for blk in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8").strip()):
        ls = blk.splitlines()
        if len(ls) >= 3 and "-->" in ls[1]:
            a, b = [x.strip() for x in ls[1].split("-->")]
            out.append((_secs(a), _secs(b), " ".join(ls[2:])))
    return out


_TAG = re.compile(r"\[[^\]]*\]|\([^)]*\)|♪[^♪]*♪|>>+")
_SPK = re.compile(r"(?:(?<=\s)|^)[A-Z][A-Z .'-]{2,}:\s")


def norm(text):
    t = _TAG.sub(" ", text)
    t = _SPK.sub(" ", t)
    t = unicodedata.normalize("NFKC", t).lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"[-–—/]", " ", t)
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    t = re.sub(r"(?<![a-z])'|'(?![a-z])", " ", t)
    return t.split()


def edit_ops(ref, hyp):
    """Levenshtein DP with backtrace -> (substitutions, deletions, insertions)."""
    n, m = len(ref), len(hyp)
    dp = np.zeros((n + 1, m + 1), dtype=np.int32)
    dp[:, 0] = np.arange(n + 1)
    dp[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        ri = ref[i - 1]
        for j in range(1, m + 1):
            dp[i, j] = min(dp[i - 1, j] + 1, dp[i, j - 1] + 1, dp[i - 1, j - 1] + (ri != hyp[j - 1]))
    i, j, s, d, ins = n, m, 0, 0, 0
    while i > 0 or j > 0:
        if i and j and dp[i, j] == dp[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            s += ref[i - 1] != hyp[j - 1]
            i -= 1
            j -= 1
        elif i and dp[i, j] == dp[i - 1, j] + 1:
            d += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return s, d, ins


# ------------------------------------------------------------------ Exp 3
e3_rows = []
digits = lambda t: sum(any(c.isdigit() for c in w) for w in t)  # noqa: E731
for r in ok:
    v = r["id"]
    man = norm(" ".join(c[2] for c in load_json3(REFS / f"{v}.manual.en.json3")))
    auto = norm(" ".join(c[2] for c in load_json3(REFS / f"{v}.auto.en.json3")))
    wh = norm(" ".join(c[2] for c in read_srt(REFS / f"{v}.whisper.srt")))
    if len(man) < 50:
        continue
    sw, dw, iw = edit_ops(man, wh)
    sa, da, ia = edit_ops(man, auto)
    sx, dx, ix = edit_ops(auto, wh)
    n = len(man)
    e3_rows.append({"id": v, "title": r["title"], "ref_words": n,
                    "wer_whisper": (sw + dw + iw) / n, "wer_auto": (sa + da + ia) / n,
                    "dis_whisper_vs_auto": (sx + dx + ix) / max(len(auto), 1),
                    "w": (sw / n, dw / n, iw / n), "a": (sa / n, da / n, ia / n),
                    "digit_tok_ref": digits(man), "digit_tok_wh": digits(wh), "digit_tok_auto": digits(auto)})
W = np.array([x["wer_whisper"] for x in e3_rows])
A = np.array([x["wer_auto"] for x in e3_rows])
refw = np.array([x["ref_words"] for x in e3_rows])
wil = stats.wilcoxon(W, A)
OUT["exp3"] = {
    "n": len(e3_rows), "ref_words": int(refw.sum()),
    "whisper": {**ms(W * 100), "ci": [x * 100 for x in boot_ci(W)], "micro": float((W * refw).sum() / refw.sum() * 100)},
    "auto": {**ms(A * 100), "ci": [x * 100 for x in boot_ci(A)], "micro": float((A * refw).sum() / refw.sum() * 100)},
    "diff_mean_pp": float(np.mean(W - A) * 100), "diff_ci": [x * 100 for x in boot_ci(W - A)],
    "whisper_better_in": int((W < A).sum()), "wilcoxon_p": float(wil.pvalue),
    "w_sdi": [float(np.mean([x["w"][k] for x in e3_rows]) * 100) for k in range(3)],
    "a_sdi": [float(np.mean([x["a"][k] for x in e3_rows]) * 100) for k in range(3)],
    "dis_whisper_vs_auto": ms([x["dis_whisper_vs_auto"] * 100 for x in e3_rows]),
    "digit_tokens": {"ref": sum(x["digit_tok_ref"] for x in e3_rows), "whisper": sum(x["digit_tok_wh"] for x in e3_rows),
                     "auto": sum(x["digit_tok_auto"] for x in e3_rows)},
    "rows": e3_rows,
}

# ------------------------------------------------------------------ Exp 2 (proxy reference)
SENT_END = re.compile(r"[.!?]+[\"')\]]*$")


def ref_boundaries(vid):
    cues = [c for c in load_json3(REFS / f"{vid}.manual.en.json3") if _TAG.sub("", c[2]).strip()]
    bounds = []
    for idx, (s, e, text) in enumerate(cues):
        words = text.split()
        total = sum(len(w) + 1 for w in words) or 1
        pos = 0
        for w in words:
            pos += len(w) + 1
            if SENT_END.search(w):
                t_end = s + (e - s) * pos / total
                nxt = cues[idx + 1][0] if (idx + 1 < len(cues) and pos == total) else t_end
                bounds.append((t_end + nxt) / 2 if nxt > t_end else t_end)
    return bounds, [(c[0], c[1]) for c in cues]


STRATS = ["llm_auto", "llm_short2", "llm_medium5", "fixed_10", "fixed_20", "fixed_60"]
TOL = [0.5, 1.0, 2.0]
e2_vid = []
for r in ok:
    rb, speech = ref_boundaries(r["id"])
    if len(rb) < 8:
        continue
    rb = np.array(rb)
    grid = np.arange(0, r["duration"], 0.05)
    entry = {"id": r["id"], "n_ref_sent": len(rb), "strat": {},
             "chance": {T: float(np.mean([np.min(np.abs(rb - g)) <= T for g in grid])) for T in TOL}}
    for sname in STRATS:
        s = r["seg"][sname]
        if "chunks" not in s:
            continue
        ch = sorted(s["chunks"])
        inner = np.array(sorted({round(c[1], 2) for c in ch[:-1]}))
        durs = np.array([c[1] - c[0] for c in ch])
        m = {"n_chunks": len(ch), "dur_mean": float(durs.mean()), "dur_sd": float(durs.std()),
             "dur_med": float(np.median(durs))}
        for T in TOL:
            if len(inner):
                prec = float(np.mean([np.min(np.abs(rb - b)) <= T for b in inner]))
                rec = float(np.mean([np.min(np.abs(inner - x)) <= T for x in rb]))
            else:
                prec, rec = float("nan"), 0.0
            m[f"prec_{T}"] = prec
            m[f"rec_{T}"] = rec
            m[f"f1_{T}"] = 2 * prec * rec / (prec + rec) if prec == prec and prec + rec > 0 else 0.0
        per = [int(np.sum((rb > c[0] + 1.0) & (rb < c[1] - 1.0))) + 1 for c in ch]
        m["sent_per_chunk_mean"] = float(np.mean(per))
        m["sent_per_chunk_max"] = int(max(per))
        m["cap2_ok"] = float(np.mean(np.array(per) <= 2))
        m["cap5_ok"] = float(np.mean(np.array(per) <= 5))
        num = den = 0.0
        for a, b in speech:
            den += b - a
            num += sum(max(0.0, min(b, c[1]) - max(a, c[0])) for c in ch)
        m["coverage"] = min(1.0, num / den) if den else float("nan")
        entry["strat"][sname] = m
    e2_vid.append(entry)

agg = {}
for sname in STRATS:
    ml = [e["strat"][sname] for e in e2_vid if sname in e["strat"]]
    if not ml:
        continue
    agg[sname] = {k: ms([m[k] for m in ml if m[k] == m[k]]) for k in ml[0]}
    agg[sname]["n_videos"] = len(ml)
    agg[sname]["prec1_ci"] = boot_ci([m["prec_1.0"] for m in ml if m["prec_1.0"] == m["prec_1.0"]])
OUT["exp2"] = {"n_videos": len(e2_vid), "excluded_no_punct": len(ok) - len(e2_vid), "tolerances": TOL, "agg": agg,
               "chance": {str(T): ms([e["chance"][T] for e in e2_vid]) for T in TOL},
               "ref_sentences": ms([e["n_ref_sent"] for e in e2_vid]),
               "excluded_ids": [r["id"] for r in ok if r["id"] not in {e["id"] for e in e2_vid}]}
pa = [(e["strat"]["llm_auto"]["prec_1.0"], e["strat"]["fixed_20"]["prec_1.0"]) for e in e2_vid
      if "llm_auto" in e["strat"] and e["strat"]["llm_auto"]["prec_1.0"] == e["strat"]["llm_auto"]["prec_1.0"]]
if len(pa) > 5:
    OUT["exp2"]["wilcoxon_auto_vs_fixed20_p"] = float(stats.wilcoxon([a for a, _ in pa], [b for _, b in pa]).pvalue)
OUT["exp2"]["per_video"] = e2_vid
json.dump(OUT, open(D / f"analysis{SUFFIX}.json", "w", encoding="utf-8"), indent=1, default=float)

summary = {k: v for k, v in OUT.items() if k not in ("exp3",)}
summary["exp2"] = {k: v for k, v in OUT["exp2"].items() if k != "per_video"}
print(json.dumps(summary, indent=1, default=float))
print(json.dumps({k: v for k, v in OUT["exp3"].items() if k != "rows"}, indent=1, default=float))
