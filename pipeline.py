# Serpapi based review fetching and summarization based on Ollama
import os
import json
import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple
import requests  # pip install requests
from serp_api_access import search_places_for_item_near_location, fetch_reviews

from sentence_transformers import SentenceTransformer, util


# ----------------------------
# Config
# ----------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

MAX_PLACES = 5
MAX_REVIEWS_PER_PLACE = 120
MAX_SNIPPETS_TO_SEND = 10

# ----------------------------
# Utilities
# ----------------------------
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str):
    # normalize lightly but don't destroy meaning
    return embed_model.encode(text, convert_to_tensor=True, normalize_embeddings=True)

def semantic_filter_reviews(reviews: list[dict], query: str, threshold: float = 0.45) -> list[dict]:
    """
    Returns reviews whose snippet is semantically similar to the query.
    threshold ~ 0.40–0.55 usually works. Start at 0.45.
    """
    q_emb = embed(query)

    kept = []
    for r in reviews:
        sn = get_review_snippet(r)
        if not sn:
            continue

        s_emb = embed(sn)
        score = float(util.cos_sim(q_emb, s_emb)[0][0])

        if score >= threshold:
            rr = dict(r)
            rr["_semantic_score"] = round(score, 3)
            kept.append(rr)

    # sort by strongest match first (nice for debugging)
    kept.sort(key=lambda x: x.get("_semantic_score", 0), reverse=True)
    return kept

def semantic_filter_reviews_expanded(reviews: list[dict], query: str, threshold: float = 0.45) -> list[dict]:
    expansions = expand_query_phi3(query)
    q_embs = [embed(q) for q in expansions[:12]]

    kept = []
    for r in reviews:
        sn = get_review_snippet(r)
        if not sn:
            continue
        s_emb = embed(sn)

        best = max(float(util.cos_sim(qe, s_emb)[0][0]) for qe in q_embs)
        if best >= threshold:
            rr = dict(r)
            rr["_semantic_score"] = round(best, 3)
            rr["_query_expansions_used"] = expansions[:12]
            kept.append(rr)

    kept.sort(key=lambda x: x.get("_semantic_score", 0), reverse=True)
    return kept


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def get_review_snippet(r: Dict) -> str:
    ex = r.get("extracted_snippet")
    if isinstance(ex, dict):
        orig = ex.get("original")
        if isinstance(orig, str) and orig.strip():
            return orig.strip()

    snip = r.get("snippet")
    if isinstance(snip, str) and snip.strip():
        return snip.strip()

    for k in ("text", "body", "review", "content"):
        v = r.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return ""

def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def token_set(s: str) -> set:
    return set(normalize_text(s).split())

def dish_matches_review(query: str, review_text: str) -> Tuple[bool, Dict]:
    """
    Smarter match:
    - multiword query: require most query tokens present anywhere in review tokens
      (paneer masala -> paneer tikka masala is OK)
    - single word: exact or fuzzy token match
    """
    q = normalize_text(query)
    q_tokens = [t for t in q.split() if len(t) >= 3]
    if not q_tokens:
        return False, {"reason": "empty_query"}

    r_tokens = token_set(review_text)

    if len(q_tokens) >= 2:
        hits = [t for t in q_tokens if t in r_tokens]
        required = len(q_tokens) if len(q_tokens) <= 2 else max(len(q_tokens) - 1, 2)

        if len(hits) >= required:
            return True, {"method": "token_overlap", "hits": hits, "required": required}

        # fuzzy fallback for typos
        fuzzy_hits = []
        for qt in q_tokens:
            if qt in r_tokens:
                fuzzy_hits.append(qt)
                continue
            found = False
            for rt in r_tokens:
                if abs(len(qt) - len(rt)) > 3:
                    continue
                if fuzzy_ratio(qt, rt) >= 0.88:
                    found = True
                    break
            if found:
                fuzzy_hits.append(qt)

        if len(fuzzy_hits) >= required:
            return True, {"method": "fuzzy_token_overlap", "hits": fuzzy_hits, "required": required}

        return False, {"method": "no_match", "best_hits": hits, "required": required}

    # single-word
    qt = q_tokens[0]
    if qt in r_tokens:
        return True, {"method": "single_exact", "hit": qt}

    for rt in r_tokens:
        if abs(len(qt) - len(rt)) > 3:
            continue
        if fuzzy_ratio(qt, rt) >= 0.90:
            return True, {"method": "single_fuzzy", "hit": rt}

    return False, {"method": "single_no_match"}

def extract_structured_reasons(review: Dict) -> List[str]:
    reasons = []
    for field in ("details", "translated_details"):
        d = review.get(field)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, str) and v.strip():
                    reasons.append(f"{k}: {v.strip()}")
    return reasons

def summarize_negative_reasons(neg_reviews: List[Dict], max_reasons: int = 4) -> List[str]:
    reasons = []
    seen = set()

    # prefer structured
    for r in neg_reviews:
        for s in extract_structured_reasons(r):
            key = normalize_text(s)
            if key and key not in seen:
                reasons.append(s)
                seen.add(key)
                if len(reasons) >= max_reasons:
                    return reasons

    # fallback to snippets
    for r in neg_reviews:
        sn = get_review_snippet(r)
        if sn:
            key = normalize_text(sn)
            if key and key not in seen:
                reasons.append(sn[:160])
                seen.add(key)
                if len(reasons) >= max_reasons:
                    break

    return reasons[:max_reasons]


# ----------------------------
# Phi-3 Mini summarizer via Ollama
# ----------------------------
def ollama_generate(prompt: str, temperature: float = 0.5) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 180
        }
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()

def phi3_summarize_place(
    place_name: str,
    item: str,
    focused_reviews: List[Dict],
    all_fetched_count: int,
) -> str:
    total = len(focused_reviews)
    if total == 0:
        return f"No reviews mentioning {item} were found in the {all_fetched_count} reviews fetched."

    # sentiment by rating
    pos = sum(1 for r in focused_reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] >= 4)
    neg = sum(1 for r in focused_reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] <= 2)

    neg_reviews = [r for r in focused_reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] <= 2]
    neg_reasons = summarize_negative_reasons(neg_reviews, max_reasons=4)

    # representative snippets
    snippets = []
    for r in focused_reviews:
        sn = get_review_snippet(r)
        if sn:
            snippets.append(sn[:320])
        if len(snippets) >= MAX_SNIPPETS_TO_SEND:
            break

    low_n_note = ""
    if total < 5:
        low_n_note = "There are only a few mentions, so be cautious and avoid strong generalizations."

    # strong instruction to avoid keyword-dump + keep grounded
    prompt = f"""
                You are writing a short, natural summary of review snippets.

                Task:
                Write ONE cohesive paragraph (3–5 sentences) about "{item}" at "{place_name}".

                Constraints:
                - Use only information supported by the snippets.
                - Do NOT output a keyword list. Do NOT use bullet points.
                - Include the count: {pos}/{total} positive mentions (among reviews mentioning the item).
                - Describe what reviewers say about taste/texture/spice/portion/value if present.
                - If there are complaints ({neg} negative), briefly mention the main reasons (use these hints if relevant): {neg_reasons if neg_reasons else "none"}.
                - {low_n_note}

                Snippets:
                {chr(10).join("- " + s for s in snippets)}
                """.strip()

    return ollama_generate(prompt, temperature=0.55)


def expand_query_phi3(query: str) -> list[str]:
    prompt = f"""
List 8-12 alternative names or closely related dishes someone might mean by: "{query}".
Return ONLY a JSON array of strings. No extra text.
Example: ["...", "..."]
""".strip()
    out = ollama_generate(prompt, temperature=0.2)

    try:
        arr = json.loads(out)
        if isinstance(arr, list):
            return [str(x) for x in arr if str(x).strip()]
    except Exception:
        pass

    return [query]

def save_reviews_to_file(place_name, reviews, suffix="reviews"):
    os.makedirs("reviews", exist_ok=True)
    filename = f"reviews/{place_name.replace(' ', '_').lower()}_{suffix}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(reviews)} reviews → {filename}")
    

# ----------------------------
# Main (UNCHANGED fetching logic)
# ----------------------------
def main():
    location = "2400 Virginia Ave NW Washington DC 20037"
    item = "Hot Chocolate"

    places = search_places_for_item_near_location(item, location, limit=MAX_PLACES)
    # with open("reviews/multiple_places_all_places.json", "r", encoding="utf-8") as f:
    #     places = json.load(f)
    if not places:
        print("No places found.")
        return

    for i, p in enumerate(places, 1):
        print(f"\n{i}. {p['title']} (rating={p.get('rating')}, reviews={p.get('reviews_count')})")
        # place_name = p["title"].lower().replace(" ", "_")

        reviews = fetch_reviews(p["data_id"], max_reviews=MAX_REVIEWS_PER_PLACE)
        # with open(f"reviews/{place_name}_all_reviews.json", "r", encoding="utf-8") as f:
        #     reviews = json.load(f)
        save_reviews_to_file(p['title'], reviews, "all_reviews")
        # focus on reviews that mention the item (semantic match)
        focused = semantic_filter_reviews_expanded(reviews, item, threshold=0.45)
        
        summary = phi3_summarize_place(
            place_name=p["title"],
            item=item,
            focused_reviews=focused,
            all_fetched_count=len(reviews),
        )
        
        print(f"   Reviews fetched: {len(reviews)} | Mentions of '{item}': {len(focused)}")
        print(f"   {summary}")


if __name__ == "__main__":
    main()
