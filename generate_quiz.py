#!/usr/bin/env python3
"""
Obsidian Daily Quiz Generator
Reads your Dermatology vault, calls Claude API, generates 30 fresh MCQs,
saves to daily_questions.json, and pushes to GitHub Pages.
"""

import os, sys, json, random, subprocess, re, textwrap, io
from datetime import date, datetime
from pathlib import Path
import anthropic

# Fix Windows console encoding so emoji/unicode don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8','utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8','utf8'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────
# CONFIG  (edit these if paths change)
# ─────────────────────────────────────────────
VAULT_PATH  = r"C:\Users\gauth\OneDrive\Documents\Dermatology venereology and leprosy"
REPO_PATH   = r"C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main"
QUESTIONS_FILE = "daily_questions.json"
ARCHIVE_DIR = "archive"

TOTAL_QUESTIONS   = 30
NOTES_TO_SAMPLE   = 15          # notes picked per run (2–3 questions each)
MAX_NOTE_CHARS    = 4000        # truncate long notes before sending
MODEL             = "claude-haiku-4-5-20251001"   # fast + cheap; upgrade to claude-sonnet-4-6 for higher quality
QUESTIONS_PER_NOTE = 2          # questions generated per note

# Exclude Obsidian system folders
EXCLUDE_DIRS = {".obsidian", ".trash", "templates", "Templates"}

# Top-level vault folders that count as "cosmetology" content
COSMETOLOGY_TOP_FOLDERS = {"cosmetology", "cosmetology review"}

# Priority sub-folders get extra weight in sampling (case-insensitive match on folder name)
# Higher weight = more notes sampled from that sub-folder = more questions
PRIORITY_SUBFOLDERS: dict[str, int] = {
    "recent advances":      4,   # 4× more likely to be sampled
    "quiz prediction model": 4,
    "stanley dermatosurgery": 3,
    "cosmetology review":   2,   # top-level folder also weighted here
}

# ─────────────────────────────────────────────
# TOPIC FOCUS PERIODS
# Add entries here to bias quiz toward specific topics.
# Format: {"topics": [...], "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "boost": N}
# boost = how many EXTRA slots these topics get in the 20-note sample
# ─────────────────────────────────────────────
FOCUS_PERIODS = [
    # Add a new entry here to bias the quiz toward specific topics for a date range.
    # Example:
    # {
    #     "label":    "Cosmetology Exclusive",
    #     "topics":   ["Cosmetology", "cosmetology review"],
    #     "from":     "2026-06-04",
    #     "to":       "2026-06-20",
    #     "exclusive": True,   # ALL notes from cosmetology only
    #     "spotters":  10,     # include N image-spotter questions per day
    # },
]

def get_active_focus(today: date):
    for fp in FOCUS_PERIODS:
        if date.fromisoformat(fp["from"]) <= today <= date.fromisoformat(fp["to"]):
            return fp
    return None

# ─────────────────────────────────────────────
# STEP 1 – collect vault files by topic
# ─────────────────────────────────────────────
def collect_files(vault: str) -> dict[str, list[Path]]:
    """Return {topic_name: [Path, ...]} for every .md in the vault."""
    vault_root = Path(vault)
    by_topic: dict[str, list[Path]] = {}
    for md in vault_root.rglob("*.md"):
        # skip obsidian internals
        if any(part in EXCLUDE_DIRS for part in md.parts):
            continue
        # topic = immediate parent folder name (or vault root label)
        topic = md.parent.name if md.parent != vault_root else "General"
        by_topic.setdefault(topic, []).append(md)
    return by_topic


def sample_notes(by_topic: dict[str, list[Path]], n: int,
                 focus=None) -> list[tuple[str, Path]]:
    """
    Sample n notes across topics.
    exclusive focus: ALL slots from focus topics only.
    boosted focus: extra slots from focus topics, rest balanced.
    """
    pool: list[tuple[str, Path]] = []

    if focus and focus.get("exclusive"):
        # 100% from focus topics
        focus_pool = [(t, p) for t in focus["topics"] if t in by_topic
                      for p in by_topic[t]]
        if not focus_pool:
            focus_pool = [(t, p) for t, paths in by_topic.items() for p in paths]
        pool = random.choices(focus_pool, k=n)
    elif focus:
        boost_topics = focus["topics"]
        boost_slots  = focus.get("boost", 8)
        boost_pool = [(t, p) for t in boost_topics if t in by_topic
                      for p in by_topic[t]]
        if boost_pool:
            pool.extend(random.choices(boost_pool, k=min(boost_slots, len(boost_pool))))
        remaining = n - len(pool)
        for topic in sorted(by_topic.keys()):
            if remaining <= 0:
                break
            pool.append((topic, random.choice(by_topic[topic])))
            remaining -= 1
    else:
        for topic in sorted(by_topic.keys()):
            pool.append((topic, random.choice(by_topic[topic])))

    # Top up if still short
    flat = [(t, p) for t, paths in by_topic.items() for p in paths]
    while len(pool) < n:
        pool.append(random.choice(flat))

    random.shuffle(pool)
    return pool[:n]


def collect_cosmetology_files(vault: str) -> dict[str, list[Path]]:
    """
    Scan the vault and return {subfolder_name: [Path, ...]} for every .md
    file whose top-level ancestor folder is in COSMETOLOGY_TOP_FOLDERS.
    Includes files at any depth under those folders.
    """
    vault_root = Path(vault)
    result: dict[str, list[Path]] = {}
    for md in vault_root.rglob("*.md"):
        if any(part in EXCLUDE_DIRS for part in md.parts):
            continue
        try:
            rel = md.relative_to(vault_root)
        except ValueError:
            continue
        if not rel.parts:
            continue
        top = rel.parts[0].lower()
        if top in COSMETOLOGY_TOP_FOLDERS:
            subtopic = md.parent.name if md.parent != vault_root else rel.parts[0]
            result.setdefault(subtopic, []).append(md)
    return result


def build_weighted_pool(cosm_files: dict[str, list[Path]]) -> list[tuple[str, Path]]:
    """
    Build a flat sampling pool where each (subfolder, path) tuple is repeated
    according to its weight in PRIORITY_SUBFOLDERS.
    Priority folders appear proportionally more often in random sampling.
    """
    pool: list[tuple[str, Path]] = []
    for subtopic, paths in cosm_files.items():
        weight = PRIORITY_SUBFOLDERS.get(subtopic.lower(), 1)
        for path in paths:
            pool.extend([(subtopic, path)] * weight)
    return pool


# ─────────────────────────────────────────────
# STEP 2 – clean & read a note
# ─────────────────────────────────────────────
def read_note(path: Path, max_chars: int = MAX_NOTE_CHARS) -> str:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ""
    # strip obsidian wiki-links [[...]] → plain text
    raw = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', raw)
    # strip inline tags  #tag
    raw = re.sub(r'(?<!\S)#\w+', '', raw)
    # collapse excessive blank lines
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()[:max_chars]


# ─────────────────────────────────────────────
# STEP 3 – call Claude to generate questions
# ─────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""
You are an expert postgraduate dermatology MCQ examiner (DNB/MD/USMLE level).
Generate factually accurate, exam-quality multiple-choice questions based ONLY
on the provided note content.
Rules:
- 4 options (A–D), exactly one correct answer
- No "all of the above" / "none of the above"
- Vary question types: direct recall, mechanism, clinical scenario, investigation
- Explanation: 2–3 factual sentences, then ONE vivid memory palace hook on a new
  line starting with "🏰 Palace: " — a ridiculous/spatial/story mnemonic anchoring
  the key fact (e.g. "🏰 Palace: Imagine a PURPLE VAMPIRE (PDL) biting BLOOD
  VESSELS in the castle hallway at 595nm")
- Return ONLY valid JSON – no commentary, no markdown fences
""").strip()

COSMETOLOGY_DIRECT_PROMPT = textwrap.dedent("""
You are an expert postgraduate cosmetology and aesthetic dermatology MCQ examiner
(DNB/MD level). Generate {n} TOUGH, original cosmetology MCQs.

Cover a MIX of these topics (vary each day based on the seed {seed}):
lasers (wavelengths, chromophores, selective photothermolysis, ablative vs
non-ablative, fractional, pulsed dye, Nd:YAG, alexandrite, CO2, Er:YAG,
IPL, picosecond), chemical peels (TCA, phenol, glycolic, salicylic, Jessner's,
depth, neutralisation, frosting), botulinum toxin (SNARE proteins, serotypes,
muscles, dilution, complications, unit conversion), dermal fillers (HA, CaHA,
PLLA, bioremodelling, Tyndall effect, vascular occlusion, hyaluronidase),
hair loss (AGA, FPHL, alopecia areata, scarring alopecias, trichoscopy,
telogen effluvium, anagen effluvium), hair transplant (FUE vs FUT, graft
survival, trichorrhexis nodosa), hair pharmacology (minoxidil SULT1A1,
finasteride/dutasteride 5-AR isoenzymes, spironolactone), PRP and LLLT,
sclerotherapy, body contouring (cryolipolysis, RF, HIFU, deoxycholic acid),
pigmentation (kojic acid, hydroquinone, azelaic acid, niacinamide, retinoids,
Kligman's formula), sunscreens (SPF, UVA/UVB, ZnO vs TiO2), vitiligo
treatment (NB-UVB vs PUVA, grafting), PDT, cosmeceuticals, laser safety.

Rules:
- 4 options per question, exactly ONE correct answer
- Distribute correct answers across positions A/B/C/D roughly evenly
- No "all of the above" / "none of the above"
- Mechanisms, clinical scenarios, and drug actions preferred over pure recall
- Explanation: 2–3 factual sentences, then ONE vivid memory palace hook on a new
  line starting with "🏰 Palace: " — a ridiculous/spatial/story mnemonic anchoring
  the single most important fact (e.g. "🏰 Palace: Imagine SULT1A1 as the CASTLE
  GATE-KEEPER who must stamp MINOXIDIL'S passport to let it work — ~35% lack the
  stamp and are non-responders")
- Return ONLY a valid JSON array — no markdown, no commentary:
[{{"q":"...","opts":["A","B","C","D"],"ans":<0-3>,"exp":"...","source":"Cosmetology","topic":"Cosmetology"}}]
""").strip()


def generate_cosmetology_direct(client: anthropic.Anthropic,
                                 n: int, today: str) -> list[dict]:
    """Generate cosmetology questions directly via API (no vault notes needed)."""
    import hashlib
    seed = int(hashlib.md5(today.encode()).hexdigest(), 16) % 10000
    prompt = COSMETOLOGY_DIRECT_PROMPT.format(n=n, seed=seed)
    print(f"\n  → No cosmetology vault notes found. Generating {n} questions via API...")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        questions = json.loads(text)
        valid = []
        for q in questions:
            if all(k in q for k in ("q", "opts", "ans", "exp")):
                if isinstance(q["opts"], list) and len(q["opts"]) == 4:
                    if isinstance(q["ans"], int) and 0 <= q["ans"] <= 3:
                        q.setdefault("source", "Cosmetology")
                        q.setdefault("topic", "Cosmetology")
                        valid.append(q)
        print(f"  → Generated {len(valid)} cosmetology questions via API")
        return valid
    except Exception as e:
        print(f"  ⚠  Direct cosmetology generation failed: {e}")
        return []

def make_questions(client: anthropic.Anthropic,
                   note_content: str,
                   note_name: str,
                   topic: str,
                   n: int = QUESTIONS_PER_NOTE) -> list[dict]:
    """Call Claude and return parsed question dicts."""
    if not note_content.strip():
        return []

    prompt = f"""Topic: {topic}
Note title: {note_name}

NOTE CONTENT:
{note_content}

Generate EXACTLY {n} MCQ(s) as a JSON array:
[
  {{
    "q": "Question text?",
    "opts": ["Option A", "Option B", "Option C", "Option D"],
    "ans": <int 0-3>,
    "exp": "Explanation sentence(s).",
    "source": "{note_name}",
    "topic": "{topic}"
  }}
]"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # strip any accidental markdown code-fence
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        questions = json.loads(text)
        # validate shape
        valid = []
        for q in questions:
            if all(k in q for k in ("q","opts","ans","exp","source","topic")):
                if isinstance(q["opts"], list) and len(q["opts"]) == 4:
                    if isinstance(q["ans"], int) and 0 <= q["ans"] <= 3:
                        valid.append(q)
        return valid
    except Exception as e:
        print(f"  ⚠  Error on '{note_name}': {e}")
        return []


# ─────────────────────────────────────────────
# STEP 3b – load image spotter questions
# ─────────────────────────────────────────────
SPOTTER_BANK = Path(REPO_PATH) / "spotter_bank.json"

def load_spotter_questions(n: int) -> list[dict]:
    """Pick n random image-based spotter/instrument questions from the bank."""
    if not SPOTTER_BANK.exists():
        print("  (spotter_bank.json not found — skipping image questions)")
        return []
    bank = json.loads(SPOTTER_BANK.read_text(encoding="utf-8"))
    all_qs = bank.get("instruments", []) + bank.get("spotters", [])
    random.shuffle(all_qs)
    return all_qs[:n]


# ─────────────────────────────────────────────
# STEP 4 – git commit & push
# ─────────────────────────────────────────────
def git_push(repo: str, message: str, token: str = "", username: str = ""):
    repo_path = Path(repo)
    os.chdir(repo_path)
    subprocess.run(["git", "add", QUESTIONS_FILE, ARCHIVE_DIR, "assets", "spotter_bank.json", "index.html"], check=False)
    result = subprocess.run(["git", "commit", "-m", message],
                            capture_output=True, text=True)
    if "nothing to commit" in result.stdout:
        print("  ℹ  Nothing new to commit.")
        return
    # push – embed token if provided
    if token and username:
        remote_url = f"https://{username}:{token}@github.com/{username}/obsidian-daily-quiz.git"
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=False)
    push = subprocess.run(["git", "push", "origin", "main"],
                          capture_output=True, text=True)
    if push.returncode == 0:
        print("  ✅  Pushed to GitHub Pages.")
    else:
        print(f"  ⚠  Push failed: {push.stderr}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # ── API key ──────────────────────────────
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        env_file = Path(REPO_PATH) / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.\n"
              "Either:\n"
              "  (a) set env var ANTHROPIC_API_KEY=sk-...\n"
              "  (b) create .env file with ANTHROPIC_API_KEY=sk-...\n")
        sys.exit(1)

    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not github_token:
        env_file = Path(REPO_PATH) / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GITHUB_TOKEN="):
                    github_token = line.split("=", 1)[1].strip().strip('"').strip("'")

    client = anthropic.Anthropic(api_key=api_key)

    today_date = date.today()
    today = str(today_date)
    print(f"\n{'='*55}")
    print(f"  Obsidian Daily Quiz Generator  —  {today}")
    print(f"{'='*55}")

    # ── check active focus period ─────────────
    focus = get_active_focus(today_date)
    spotter_count = 0
    if focus:
        days_left = (date.fromisoformat(focus["to"]) - today_date).days + 1
        mode = "EXCLUSIVE" if focus.get("exclusive") else "BOOST"
        print(f"\nFOCUS MODE ({mode}): {focus['label']}")
        print(f"   Topics: {', '.join(focus['topics'])}")
        print(f"   {days_left} days remaining (until {focus['to']})")
        spotter_count = focus.get("spotters", 0)
        if spotter_count:
            print(f"   Image spotter questions per day: {spotter_count}")
    else:
        print(f"\nMode: Balanced (all topics)")

    # ── collect & sample notes ────────────────
    print(f"\n📂 Scanning vault: {VAULT_PATH}")
    by_topic = collect_files(VAULT_PATH)
    total_notes = sum(len(v) for v in by_topic.values())
    print(f"   Found {total_notes} notes across {len(by_topic)} topics")
    print(f"   Topics: {', '.join(sorted(by_topic.keys()))}")

    # ── load image spotter questions first ───
    spotter_qs = load_spotter_questions(spotter_count) if spotter_count else []
    if spotter_qs:
        print(f"\nLoaded {len(spotter_qs)} image spotter questions")

    # ── generate AI text questions ────────────
    text_target = TOTAL_QUESTIONS - len(spotter_qs)
    all_questions: list[dict] = []

    if focus and focus.get("exclusive"):
        # ── Priority-weighted cosmetology sampling ───────────────────────────
        # Collect ALL files under COSMETOLOGY_TOP_FOLDERS (any depth / subfolder)
        cosm_files = collect_cosmetology_files(VAULT_PATH)

        if cosm_files:
            weighted_pool = build_weighted_pool(cosm_files)
            random.shuffle(weighted_pool)
            sampled = weighted_pool[:NOTES_TO_SAMPLE]

            # Show subfolder breakdown
            from collections import Counter as _Counter
            sf_counts = _Counter(t for t, _ in sampled)
            print(f"\n📝 Sampled {len(sampled)} cosmetology notes (priority-weighted):")
            for sf, cnt in sorted(sf_counts.items(), key=lambda x: -x[1]):
                wt = PRIORITY_SUBFOLDERS.get(sf.lower(), 1)
                bar = "█" * cnt
                print(f"   {sf:<40} {bar} {cnt}  (×{wt})")

            for i, (topic, path) in enumerate(sampled, 1):
                if len(all_questions) >= text_target:
                    break
                needed = min(QUESTIONS_PER_NOTE, text_target - len(all_questions))
                print(f"   [{i:02d}/{len(sampled)}] {topic[:30]:<30} / {path.stem[:35]:<35} ", end="", flush=True)
                content = read_note(path)
                if not content:
                    print("⚠  empty")
                    continue
                qs = make_questions(client, content, path.stem, topic, needed)
                print(f"→ +{len(qs)}")
                all_questions.extend(qs)
        else:
            # No cosmetology vault files found — fall back to direct API generation
            print("\n  ⚠  No cosmetology notes found in vault — generating via API...")
            all_questions = generate_cosmetology_direct(client, text_target, today)
            sampled = []
    else:
        # ── Balanced sampling across all topics ──────────────────────────────
        sampled = sample_notes(by_topic, NOTES_TO_SAMPLE, focus=focus)
        print(f"\n📝 Sampled {len(sampled)} notes for today's quiz")

        for i, (topic, path) in enumerate(sampled, 1):
            if len(all_questions) >= text_target:
                break
            needed = min(QUESTIONS_PER_NOTE, text_target - len(all_questions))
            print(f"   [{i:02d}/{len(sampled)}] {topic} / {path.stem[:45]:<45} ", end="", flush=True)
            content = read_note(path)
            if not content:
                print("⚠  empty")
                continue
            qs = make_questions(client, content, path.stem, topic, needed)
            print(f"→ +{len(qs)} question{'s' if len(qs)!=1 else ''}")
            all_questions.extend(qs)

    # ── merge spotters + AI text questions ───
    all_questions.extend(spotter_qs)
    random.shuffle(all_questions)
    all_questions = all_questions[:TOTAL_QUESTIONS]

    if len(all_questions) < TOTAL_QUESTIONS:
        print(f"\nOnly generated {len(all_questions)}/{TOTAL_QUESTIONS} questions.")

    # ── save JSON ─────────────────────────────
    output = {
        "date": today,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(all_questions),
        "topics_covered": sorted(list({q["topic"] for q in all_questions})),
        "questions": all_questions
    }
    out_path = Path(REPO_PATH) / QUESTIONS_FILE
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Saved {len(all_questions)} questions → {QUESTIONS_FILE}")

    # ── archive a copy ────────────────────────
    archive_dir = Path(REPO_PATH) / ARCHIVE_DIR
    archive_dir.mkdir(exist_ok=True)
    archive_file = archive_dir / f"{today}.json"
    archive_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"📚 Archived → archive/{today}.json")

    # ── topic summary ─────────────────────────
    from collections import Counter
    topic_count = Counter(q["topic"] for q in all_questions)
    print(f"\n📊 Topics in today's quiz:")
    for topic, count in sorted(topic_count.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"   {topic:<35} {bar} {count}")

    # ── git push ──────────────────────────────
    print(f"\n🚀 Pushing to GitHub Pages…")
    run_time = datetime.now().strftime("%H:%M")
    focus_label = f" [{focus['label']}]" if focus else ""
    git_push(REPO_PATH,
             f"Quiz {today} {run_time} — {len(all_questions)} cosmetology Qs{focus_label}",
             github_token, "gauthamkrishna0730-png")

    print(f"\n✅ Done! Visit your quiz at:")
    print(f"   https://gauthamkrishna0730-png.github.io/obsidian-daily-quiz/")
    print()


if __name__ == "__main__":
    main()
