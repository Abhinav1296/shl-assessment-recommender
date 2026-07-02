"""
catalog.py
Loads and preprocesses the SHL product catalog.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

CATALOG_PATH = Path(__file__).parent / "shl_catalog.json"

# Map SHL 'keys' (category strings) to test_type codes used in traces.
# Codes: K, P, A, S, B, C, D
KEY_TO_CODE = {
    "Knowledge & Skills": "K",
    "Personality & Behavior": "P",
    "Ability & Aptitude": "A",
    "Simulations": "S",
    "Biodata & Situational Judgment": "B",
    "Competencies": "C",
    "Development & 360": "D",
    "Assessment Exercises": "E",
}


def derive_test_type(keys: List[str]) -> str:
    """Convert list of 'keys' into a comma-separated code string.
    Example: ['Knowledge & Skills', 'Simulations'] -> 'K,S'
    """
    codes = []
    for k in keys or []:
        code = KEY_TO_CODE.get(k)
        if code and code not in codes:
            codes.append(code)
    return ",".join(codes) if codes else "-"


def load_catalog() -> List[Dict[str, Any]]:
    """Load catalog JSON and enrich each item with derived fields."""
    with open(CATALOG_PATH, encoding="utf-8") as f:
        data = json.load(f, strict=False)

    enriched = []
    for item in data:
        # Guard against missing fields
        name = (item.get("name") or "").strip()
        link = (item.get("link") or "").strip()
        desc = (item.get("description") or "").strip()
        keys = item.get("keys") or []
        job_levels = item.get("job_levels") or []
        languages = item.get("languages") or []
        duration = (item.get("duration") or "").strip()

        # Skip garbage items with no name or link
        if not name or not link:
            continue

        # Build a single searchable text blob (used by retriever)
        blob_parts = [
            name,
            desc,
            " ".join(keys),
            " ".join(job_levels),
        ]
        search_text = " | ".join([p for p in blob_parts if p]).lower()

        enriched.append({
            "entity_id": item.get("entity_id", ""),
            "name": name,
            "link": link,
            "url": link,  # alias — spec uses "url"
            "description": desc,
            "keys": keys,
            "test_type": derive_test_type(keys),
            "job_levels": job_levels,
            "languages": languages,
            "duration": duration,
            "remote": item.get("remote", ""),
            "adaptive": item.get("adaptive", ""),
            "search_text": search_text,
        })

    return enriched


# ---- URL validator (for guardrails) ----

_valid_urls_cache = None


def get_valid_urls() -> set:
    """Return set of all valid catalog URLs. Used to reject hallucinated URLs."""
    global _valid_urls_cache
    if _valid_urls_cache is None:
        _valid_urls_cache = {item["link"] for item in load_catalog()}
    return _valid_urls_cache


# ---- Quick standalone test ----
if __name__ == "__main__":
    items = load_catalog()
    print(f"Loaded {len(items)} items.")
    print("\nSample item:")
    sample = items[0]
    for k, v in sample.items():
        if k == "search_text":
            print(f"  {k}: {v[:100]}...")
        else:
            print(f"  {k}: {v}")

    # Distribution of test types
    from collections import Counter
    type_counts = Counter()
    for item in items:
        for code in item["test_type"].split(","):
            type_counts[code] += 1
    print("\nTest type distribution:")
    for code, count in type_counts.most_common():
        print(f"  {code}: {count}")