"""Corpus discovery: public-domain (US-government) YouTube videos that have
BOTH human-made English captions and YouTube auto captions, 2-8 min long."""
import json, sys
import yt_dlp

CHANNELS = {
    "NASA": "https://www.youtube.com/@NASA/videos",
    "NASA Goddard": "https://www.youtube.com/@NASAGoddard/videos",
    "NASA Johnson": "https://www.youtube.com/@NASAJohnson/videos",
    "NOAA": "https://www.youtube.com/@NOAA/videos",
    "USGS": "https://www.youtube.com/@USGS/videos",
    "NIH": "https://www.youtube.com/@NIH/videos",
    "Library of Congress": "https://www.youtube.com/@LibraryOfCongress/videos",
    "National Archives": "https://www.youtube.com/@usnationalarchives/videos",
    "US Dept of Energy": "https://www.youtube.com/@ENERGY/videos",
    "NPS": "https://www.youtube.com/@NationalParkService/videos",
    "NASA Jet Propulsion Lab": "https://www.youtube.com/@NASAJPL/videos",
    "US Navy": "https://www.youtube.com/@usnavy/videos",
}
out = []
flat = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": 40}
full = {"quiet": True, "no_warnings": True, "skip_download": True}
seen = set()
for name, url in CHANNELS.items():
    try:
        with yt_dlp.YoutubeDL(flat) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        print("channel fail", name, str(e)[:80]); continue
    cands = [e for e in info.get("entries", []) if e and e.get("duration") and 120 <= e["duration"] <= 480]
    print(name, len(cands), "candidates", flush=True)
    kept = 0
    for e in cands:
        if e["id"] in seen or kept >= 6:
            continue
        seen.add(e["id"])
        try:
            with yt_dlp.YoutubeDL(full) as y:
                v = y.extract_info("https://www.youtube.com/watch?v=" + e["id"], download=False)
        except Exception as ex:
            print("  skip", e["id"], str(ex)[:60]); continue
        manual = "en" in (v.get("subtitles") or {})
        auto = any(k == "en" or k.startswith("en-") for k in (v.get("automatic_captions") or {}))
        if manual and auto:
            out.append({"id": e["id"], "title": v["title"], "channel": name, "duration": v["duration"],
                        "license": v.get("license"), "lang": v.get("language")})
            kept += 1
            print("  OK", e["id"], int(v["duration"]), v["title"][:50], flush=True)
    json.dump(out, open("data/corpus_candidates.json", "w"), indent=1)
print("total", len(out))
