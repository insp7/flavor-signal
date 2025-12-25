from serpapi import GoogleSearch
from typing import List, Dict

# API_KEY
SERPAPI_API_KEY = "YOUR_API_KEY"

# ----------------------------
# SerpAPI: search places + fetch reviews
# ----------------------------
def search_places_for_item_near_location(item: str, location: str, limit: int = 5) -> List[Dict]:
    params = {
        "engine": "google_maps",
        "q": f"{item} near {location}",
        "api_key": SERPAPI_API_KEY,
    }
    results = GoogleSearch(params).get_dict()

    places = []
    for it in (results.get("local_results") or []):
        title = it.get("title") or it.get("name")
        data_id = it.get("data_id")
        rating = it.get("rating")
        reviews_count = it.get("reviews")
        if title and data_id:
            places.append({
                "title": title,
                "data_id": data_id,
                "rating": rating,
                "reviews_count": reviews_count,
            })
        if len(places) >= limit:
            break

    return places

def fetch_reviews(data_id: str, max_reviews: int = 100) -> List[Dict]:
    reviews: List[Dict] = []
    params = {
        "engine": "google_maps_reviews",
        "data_id": data_id,
        "api_key": SERPAPI_API_KEY,
    }

    while True:
        results = GoogleSearch(params).get_dict()
        batch = results.get("reviews", []) or []
        reviews.extend(batch)

        if len(reviews) >= max_reviews:
            break

        next_token = (results.get("serpapi_pagination") or {}).get("next_page_token")
        if not next_token:
            break
        params["next_page_token"] = next_token

    return reviews[:max_reviews]