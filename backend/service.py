# backend/service.py
import os, json, re
from typing import List, Dict

from serp_api_access import search_places_for_item_near_location, fetch_reviews
from sentence_transformers import SentenceTransformer, util
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

MAX_PLACES = 7
MAX_REVIEWS_PER_PLACE = 100
MAX_SNIPPETS_TO_SEND = 10

embed_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str):
    return embed_model.encode(text, convert_to_tensor=True, normalize_embeddings=True)

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

def ollama_generate(prompt: str, temperature: float = 0.5) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 180},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return (r.json().get("response") or "").strip()

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
            kept.append(rr)

    kept.sort(key=lambda x: x.get("_semantic_score", 0), reverse=True)
    return kept

def phi3_summarize_place(place_name: str, item: str, focused_reviews: List[Dict], all_fetched_count: int) -> str:
    total = len(focused_reviews)
    if total == 0:
        return f"No reviews mentioning {item} were found in the {all_fetched_count} reviews fetched."

    pos = sum(1 for r in focused_reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] >= 4)
    neg = sum(1 for r in focused_reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] <= 2)

    snippets = []
    for r in focused_reviews:
        sn = get_review_snippet(r)
        if sn:
            snippets.append(sn[:320])
        if len(snippets) >= MAX_SNIPPETS_TO_SEND:
            break

    low_n_note = "There are only a few mentions, so be cautious and avoid strong generalizations." if total < 5 else ""

    prompt = f"""
        You are writing a short, natural summary of review snippets.

        Write ONE cohesive paragraph (3–5 sentences) about "{item}" at "{place_name}".

        Constraints:
        - Use only information supported by the snippets.
        - Do NOT output a keyword list. Do NOT use bullet points.
        - Include the count: {pos}/{total} positive mentions (among reviews mentioning the item).
        - Describe what reviewers say about taste/texture/spice/portion/value if present.
        - If there are complaints ({neg} negative), briefly mention them.
        - {low_n_note}

        Snippets:
        {chr(10).join("- " + s for s in snippets)}
        """.strip()

    return ollama_generate(prompt, temperature=0.55)

def phi3_summarize_batch(item: str, batch: List[Dict]) -> Dict[str, str]:
    """
    batch: list of dicts:
      {
        "place": "<place title>",
        "pos": int,
        "neg": int,
        "total": int,
        "all_fetched_count": int,
        "snippets": [str, ...]
      }
    returns: { "<place title>": "<summary>", ... }
    """

    # Keep prompt compact (speed). Also reduce generation length.
    # You can tune num_predict in ollama_generate() too; see note at bottom.
    prompt = f"""
        You will write short, natural summaries of review snippets for ONE dish.

        Dish: "{item}"

        Return ONLY valid JSON in this exact format:
        {{
        "summaries": [
            {{"place": "PLACE_NAME", "summary": "ONE PARAGRAPH"}}
        ]
        }}

        Rules:
        - For each place in the input, write 1 paragraph (2–4 sentences).
        - Use ONLY information supported by snippets.
        - No bullet points. No headings.
        - Include the count: POS/TOTAL positive mentions (among reviews mentioning the dish).
        - If there are complaints (NEG negative), briefly mention them.
        - If TOTAL == 0, set summary to: "No reviews mentioning {item} were found in the ALL_FETCHED reviews fetched."
        - Be concise.

        Input JSON:
        {json.dumps({"item": item, "places": batch}, ensure_ascii=False)}
        """.strip()

    out = ollama_generate(prompt, temperature=0.45)

    try:
        data = json.loads(out)
        arr = data.get("summaries", [])
        if isinstance(arr, list):
            m = {}
            for x in arr:
                if isinstance(x, dict):
                    place = str(x.get("place") or "").strip()
                    summary = str(x.get("summary") or "").strip()
                    if place and summary:
                        m[place] = summary
            return m
    except Exception:
        pass

    # Fallback: if model returns non-JSON, return empty mapping
    return {}

def run(location: str, item: str) -> dict:
    places = search_places_for_item_near_location(item, location, limit=MAX_PLACES) or []
    # with open("reviews/multiple_places_all_places.json", "r", encoding="utf-8") as f:
    #     places = json.load(f)
    if not places:
        return {"location": location, "item": item, "results": []}

    results = []
    for p in places:
        title = p.get("title") or "Unknown place"
        data_id = p.get("data_id")
        if not data_id:
            continue  # skip broken entries
        
        # place_name = p["title"].lower().replace(" ", "_")
        # with open(f"reviews/{place_name}_all_reviews.json", "r", encoding="utf-8") as f:
        #     reviews = json.load(f)

        reviews = fetch_reviews(data_id, max_reviews=MAX_REVIEWS_PER_PLACE) or []

        focused = semantic_filter_reviews_expanded(reviews, item, threshold=0.45)

        summary = phi3_summarize_place(
            place_name=title,
            item=item,
            focused_reviews=focused,
            all_fetched_count=len(reviews),
        )

        results.append({
            "place": {
                "title": title,
                "rating": p.get("rating"),
                "reviews_count": p.get("reviews_count"),
            },
            "reviews_fetched": len(reviews),
            "mentions": len(focused),
            "summary": summary,
        })

    return {"location": location, "item": item, "results": results}

