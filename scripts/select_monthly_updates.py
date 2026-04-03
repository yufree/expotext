#!/usr/bin/env python3

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_FILE = DATA_DIR / "papers.json"
OUTPUT_FILE = DATA_DIR / "selected-updates.json"

MAX_RETRIES = 3
BACKOFF_BASE = 2

PRIORITY_JOURNALS = {
    "Nature",
    "Science",
    "Nature Communications",
    "Environmental Health Perspectives",
    "International Journal of Hygiene and Environmental Health",
    "Journal of Exposure Science & Environmental Epidemiology",
    "Environmental Science & Technology",
    "PLOS ONE",
    "The Lancet Planetary Health",
    "Environment International",
}


def load_papers():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Papers file not found: {INPUT_FILE}. "
            "Run fetch_monthly_papers.py first."
        )
    data = json.loads(INPUT_FILE.read_text())
    if "month" not in data or "papers" not in data:
        raise ValueError(
            f"Invalid papers.json structure: missing 'month' or 'papers' key"
        )
    return data


def score_paper(paper):
    text = " ".join(
        [
            paper.get("title", ""),
            paper.get("abstract", ""),
            " ".join(paper.get("publication_types", [])),
        ]
    ).lower()
    title = paper.get("title", "").lower()
    score = 0

    if "exposome" in text or "exposomics" in text:
        score += 10
    if paper.get("journal") in PRIORITY_JOURNALS:
        score += 8
    if any(
        token in text
        for token in ["review", "perspective", "consensus", "guideline", "framework"]
    ):
        score += 8
    if any(
        token in text
        for token in [
            "network",
            "platform",
            "resource",
            "consortium",
            "cohort",
            "infrastructure",
        ]
    ):
        score += 8
    if any(
        token in text
        for token in ["workflow", "standard", "best practice", "harmon", "benchmark"]
    ):
        score += 7
    if any(
        token in text
        for token in ["ewas", "exwas", "environment-wide association"]
    ):
        score += 6
    if any(
        token in text
        for token in [
            "metabolomics",
            "multi-omics",
            "biomarker",
            "adduct",
            "exposure biomarker",
        ]
    ):
        score += 5
    if any(
        token in text
        for token in [
            "environmental justice",
            "discrimination",
            "neighborhood",
            "social determinant",
        ]
    ):
        score += 5
    if any(
        token in title for token in ["case report", "protocol", "conference abstract"]
    ):
        score -= 10
    if any(
        pub_type.lower() == "review"
        for pub_type in paper.get("publication_types", [])
    ):
        score += 5
    return score


def choose_section(paper):
    text = " ".join([paper.get("title", ""), paper.get("abstract", "")]).lower()
    if any(
        token in text
        for token in ["ewas", "exwas", "environment-wide association"]
    ):
        return "Exposome-wide association studies"
    if any(
        token in text
        for token in ["network", "platform", "resource", "consortium", "coordination"]
    ):
        return "Core study designs and flagship projects"
    if any(
        token in text
        for token in ["justice", "discrimination", "neighborhood", "social determinant"]
    ):
        return "Environmental justice is central, not optional"
    if any(
        token in text
        for token in [
            "metabolomics",
            "multi-omics",
            "biomarker",
            "adductomics",
            "internal exposure",
        ]
    ):
        return "Internal exposure in more detail"
    if any(
        token in text
        for token in [
            "exposure science",
            "air pollution",
            "water",
            "external exposure",
            "geospatial",
        ]
    ):
        return "External exposure in more detail"
    if any(
        token in text
        for token in ["review", "framework", "standard", "best practice", "workflow"]
    ):
        return "How exposome research is done in practice"
    return "Main limitations of the field"


def summarize_fallback(paper):
    section = choose_section(paper)
    title = paper.get("title", "Untitled paper")
    journal = paper.get("journal", "the literature")
    if section == "Core study designs and flagship projects":
        return (
            f"{title} appears relevant because it describes research coordination, "
            f"infrastructure, or platform-scale organization for exposomics in {journal}."
        )
    if section == "Exposome-wide association studies":
        return (
            f"{title} appears relevant because it advances or applies large-scale "
            "association logic for linking exposures to health outcomes."
        )
    if section == "Internal exposure in more detail":
        return (
            f"{title} appears relevant because it connects exposome research "
            "to internal molecular measurement, especially biomarkers or omics readouts."
        )
    if section == "External exposure in more detail":
        return (
            f"{title} appears relevant because it develops measurement "
            "or interpretation of environmental exposures outside the body."
        )
    return (
        f"{title} appears relevant to the exposome field because it may "
        "influence current methods, standards, or interpretation."
    )


def llm_available():
    return bool(os.environ.get("LLM_API_KEY")) and bool(
        os.environ.get("LLM_MODEL")
    )


def extract_json_block(text):
    """Extract a JSON object from LLM response, handling markdown fences."""
    cleaned = text.strip()

    # Strip markdown code fences if present
    fence_pattern = re.compile(r"^```(?:json)?\s*\n(.*?)\n\s*```$", re.S)
    fence_match = fence_pattern.search(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to finding the outermost JSON object via brace matching
    start_idx = cleaned.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object found in LLM response")

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start_idx, len(cleaned)):
        ch = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start_idx : i + 1])
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Found JSON-like block but it failed to parse: {exc}"
                    ) from exc

    raise ValueError("No complete JSON object found in LLM response")


def validate_llm_updates(updates):
    """Validate that LLM-returned updates have the expected structure."""
    if not isinstance(updates, list):
        print(
            f"  LLM returned non-list updates type: {type(updates).__name__}",
            file=sys.stderr,
        )
        return []
    required_keys = {"title", "url", "section", "summary"}
    validated = []
    for i, update in enumerate(updates):
        if not isinstance(update, dict):
            print(f"  Skipping non-dict update at index {i}", file=sys.stderr)
            continue
        missing = required_keys - set(update.keys())
        if missing:
            print(
                f"  Skipping update '{update.get('title', '?')}': missing {missing}",
                file=sys.stderr,
            )
            continue
        validated.append(update)
    return validated


def _scrub_key(message):
    """Remove API key fragments from error messages."""
    api_key = os.environ.get("LLM_API_KEY", "")
    if api_key and api_key in str(message):
        return str(message).replace(api_key, "***REDACTED***")
    return str(message)


def call_llm(candidates, month):
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ["LLM_API_KEY"]
    model = os.environ["LLM_MODEL"]

    prompt = {
        "month": month,
        "task": (
            "Select at most 5 papers that are textbook-worthy updates for a public exposome webpage. "
            "Keep only papers that change field understanding, standards, infrastructure, core methods, "
            "major cohorts, or broadly useful reviews. Reject narrow incremental studies."
        ),
        "required_output_schema": {
            "updates": [
                {
                    "title": "paper title",
                    "url": "doi or official url",
                    "section": "matching section heading from the webpage",
                    "importance": "high or medium",
                    "summary": "2-3 sentence textbook-style summary",
                    "why_it_matters": "1 sentence",
                }
            ]
        },
        "candidates": candidates,
    }

    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are curating a textbook-style exposome webpage. "
                    "Return strict JSON only (no markdown fences). Be conservative. Prefer major reviews, standards, "
                    "platforms, cohorts, and field-shaping papers over narrow application studies."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "exposome-monthly-updater/1.0",
        },
        method="POST",
    )

    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            content = payload["choices"][0]["message"]["content"]
            parsed = extract_json_block(content)
            raw_updates = parsed.get("updates", [])
            return validate_llm_updates(raw_updates)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE ** (attempt + 1)
                print(
                    f"  LLM retry {attempt + 1}/{MAX_RETRIES} after {wait}s: {_scrub_key(exc)}",
                    file=sys.stderr,
                )
                time.sleep(wait)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            # Don't retry on parse errors — the response is what it is
            print(f"  LLM response parse error: {_scrub_key(exc)}", file=sys.stderr)
            return []

    print(
        f"  LLM call failed after {MAX_RETRIES} attempts: {_scrub_key(last_exc)}",
        file=sys.stderr,
    )
    return []


def main():
    data = load_papers()
    month = data["month"]
    papers = data["papers"]
    print(f"Scoring {len(papers)} papers for {month}")

    ranked = []
    for paper in papers:
        paper_copy = dict(paper)
        paper_copy["score"] = score_paper(paper)
        paper_copy["suggested_section"] = choose_section(paper_copy)
        ranked.append(paper_copy)
    ranked.sort(
        key=lambda item: (item["score"], item.get("published_date", ""), item["title"]),
        reverse=True,
    )

    candidates = []
    for paper in ranked[:25]:
        candidates.append(
            {
                "title": paper["title"],
                "journal": paper.get("journal", ""),
                "published_date": paper.get("published_date", ""),
                "url": paper.get("url", ""),
                "doi": paper.get("doi", ""),
                "publication_types": paper.get("publication_types", []),
                "score": paper["score"],
                "suggested_section": paper["suggested_section"],
                "abstract": paper.get("abstract", "")[:2500],
            }
        )

    if llm_available():
        print("  LLM configured — running automatic selection")
        updates = call_llm(candidates, month)
        mode = "llm" if updates else "llm_no_results"
    else:
        print("  LLM not configured — generating review queue only")
        updates = []
        mode = "review_queue_only"

    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "month": month,
        "mode": mode,
        "updates": updates,
        "review_queue": [
            {
                "title": paper["title"],
                "url": paper["url"],
                "section": paper["suggested_section"],
                "score": paper["score"],
                "summary": summarize_fallback(paper),
            }
            for paper in ranked[:10]
        ],
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote monthly selection data to {OUTPUT_FILE} (mode: {mode})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"select_monthly_updates.py failed: {exc}", file=sys.stderr)
        raise
