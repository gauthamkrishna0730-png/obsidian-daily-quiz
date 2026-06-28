#!/usr/bin/env python3
"""
Build spotter_bank.json from memory-castle instruments.js and spotters.js.
Run once (or after updating memory-castle) to refresh the image question bank.
"""

import json, random, subprocess, sys
from pathlib import Path

MEMORY_CASTLE = Path("D:/claude code/memory-castle")
OUT = Path(r"C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main\spotter_bank.json")

# ── use Node to eval the JS files ────────────────────────────────────────────
def load_js(varname: str, jsfile: Path) -> dict:
    script = f"""
const fs = require('fs');
eval(fs.readFileSync({json.dumps(str(jsfile))}, 'utf8').replace('window.', 'global.'));
process.stdout.write(JSON.stringify(global.{varname}));
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Node error: {r.stderr}"); sys.exit(1)
    return json.loads(r.stdout)


def make_distractors(correct: str, pool: list[str], n: int = 3) -> list[str]:
    others = [x for x in pool if x != correct]
    random.shuffle(others)
    return others[:n]


QUIZ_ROOT = Path(r"C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main")

def img_exists(path: str) -> bool:
    return (QUIZ_ROOT / path).exists()

def build_instrument_questions(instr_data: dict) -> list[dict]:
    all_items = [(cat["name"], item) for cat in instr_data["categories"]
                 for item in cat["items"] if item.get("img") and img_exists(item["img"])]
    all_names = [item["name"] for _, item in all_items]

    questions = []
    for cat_name, item in all_items:
        correct = item["name"]
        facts = item.get("facts", [])
        exp_text = ". ".join(f.replace("**", "") for f in facts[:2]) if facts else correct
        distractors = make_distractors(correct, all_names)
        if len(distractors) < 3:
            continue
        opts = distractors + [correct]
        random.shuffle(opts)
        ans_idx = opts.index(correct)
        questions.append({
            "q": "Identify the surgical instrument shown in the image:",
            "opts": opts,
            "ans": ans_idx,
            "exp": exp_text,
            "source": f"ACSI Instruments – {cat_name}",
            "topic": "Cosmetology",
            "image": item["img"],
            "image_type": "instrument",
        })
    return questions


def build_spotter_questions(spot_data: dict) -> list[dict]:
    all_items = [(cat["name"], item) for cat in spot_data["categories"]
                 for item in cat["items"] if item.get("img") and img_exists(item["img"])]
    all_names = [item["name"] for _, item in all_items]

    q_templates = {
        "Eminent Figures":         "Identify the eminent figure shown:",
        "Clinical Signs & Pathology": "Identify the clinical sign / pathological finding shown:",
        "Lines & Landmarks":       "Identify the anatomical line or landmark shown:",
        "Misc":                    "Identify the item shown:",
    }

    questions = []
    for cat_name, item in all_items:
        correct = item["name"]
        facts = item.get("facts", [])
        exp_text = ". ".join(f.replace("**", "") for f in facts[:2]) if facts else correct
        distractors = make_distractors(correct, all_names)
        if len(distractors) < 3:
            continue
        opts = distractors + [correct]
        random.shuffle(opts)
        ans_idx = opts.index(correct)
        q_stem = q_templates.get(cat_name, "Identify the item shown:")
        questions.append({
            "q": q_stem,
            "opts": opts,
            "ans": ans_idx,
            "exp": exp_text,
            "source": f"ACSI Spotters – {cat_name}",
            "topic": "Cosmetology",
            "image": item["img"],
            "image_type": "spotter",
        })
    return questions


def main():
    print("Loading instruments.js …")
    instr = load_js("INSTRUMENTS", MEMORY_CASTLE / "data" / "instruments.js")
    print("Loading spotters.js …")
    spot  = load_js("SPOTTERS",    MEMORY_CASTLE / "data" / "spotters.js")

    random.seed(42)
    instr_qs  = build_instrument_questions(instr)
    spotter_qs = build_spotter_questions(spot)

    bank = {
        "total": len(instr_qs) + len(spotter_qs),
        "instruments": instr_qs,
        "spotters": spotter_qs,
    }
    OUT.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(instr_qs)} instrument + {len(spotter_qs)} spotter questions -> {OUT}")


if __name__ == "__main__":
    main()
