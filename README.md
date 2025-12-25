# FlavorSignal — Cut through the noise

When you search for a specific dish near you—say on Google Maps—you’re shown a list of restaurants. To decide what to order, you start reading reviews, only to realize most of them talk about the restaurant in general, not the dish you’re actually interested in. Finding real opinions about that one item means scrolling endlessly and hoping someone mentions it.

FlavorSignal solves this by analyzing reviews at the dish level. It identifies and summarizes opinions specifically about the item you’re searching for, so you don’t have to read everything yourself. Instead of raw reviews, users get a clear, concise summary that helps them decide quickly and confidently.

By extracting a clear signal from noisy reviews, FlavorSignal helps users cut through the noise.

## Features
- Find nearby restaurants that serve the dish you’re looking for.
- Summarize only the reviews that actually mention your dish—even when people use different names or terms (e.g., searches for hot chocolate also capture mentions of hot cocoa) i.e. semantic filtering before summarization.
- Get a clear, item-level summary with key positives, negatives, and common complaints, so you can decide without reading every review.

## APIs used
- SerpAPI Google Maps and Google Maps Reviews endpoints for place search and review retrieval.
- Ollama local generation HTTP API (defaults to `phi3:mini`).

## Setup
1) Create a virtual environment (optional but recommended).
2) Install core deps: `pip install serpapi requests sentence-transformers`.
3) Environment variables:
   - `SERPAPI_API_KEY` (required) – your SerpAPI key for Google Maps endpoints.
   - `OLLAMA_URL` (default `http://localhost:11434/api/generate`).
   - `OLLAMA_MODEL` (default `phi3:mini`).
4) Ensure Ollama is installed and running and the chosen model is available.

## Running the main flow
1) Edit `location` and `item` near the bottom of `pipeline.py` to the place and dish you want.
2) Run: `python pipeline.py`.
   - The script searches for places, fetches up to 120 reviews each, saves them under `reviews/{place}_all_reviews.json`, filters for mentions of your item, and prints a natural-language summary per place.

## Directory structure
- `pipeline.py` – semantic filtering + summarization pipeline.
- `serp_api_access.py` – SerpAPI helpers to search places and fetch reviews.
- `reviews/` – example JSON review dumps; scripts write new files here.
