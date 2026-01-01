# Flavor Signal — Cut through the noise

When you search for a specific dish near you—say on Google Maps—you’re shown a list of restaurants. To decide what to order, you start reading reviews, only to realize most of them talk about the restaurant in general, not the dish you’re actually interested in. Finding real opinions about that one item means scrolling endlessly and hoping someone mentions it.

FlavorSignal solves this by analyzing reviews at the dish level. It identifies and summarizes opinions specifically about the item you’re searching for, so you don’t have to read everything yourself. Instead of raw reviews, users get a clear, concise summary that helps them decide quickly and confidently.

By extracting a clear signal from noisy reviews, FlavorSignal helps users cut through the noise.

## Interface Preview

Below are screenshots of the current Flavor Signal interface, showcasing the minimal UI and item-specific review summaries.

<p align="center">
  <img src="https://github.com/insp7/flavor-signal/blob/master/public/images/pic7.PNG" alt="Flavor Signal – Search & Input UI">
</p>

<p align="center">
  <img src="https://github.com/insp7/flavor-signal/blob/master/public/images/pic4.PNG" alt="Flavor Signal – Item-Specific Review Summaries">
</p>

<p align="center">
  <img src="https://github.com/insp7/flavor-signal/blob/master/public/images/pic6.PNG" alt="Flavor Signal – Full Page">
</p>

## APIs used
- SerpAPI Google Maps and Google Maps Reviews endpoints for place search and review retrieval.
- Ollama local generation HTTP API (defaults to `phi3:mini`).

## Setup
1) Create a virtual environment (optional but recommended).
2) Install core deps: `pip install serpapi requests sentence-transformers` OR better just install as per requirements.txt.
3) Environment variables:
   - `SERPAPI_API_KEY` (required) – your SerpAPI key for Google Maps endpoints.
   - `OLLAMA_URL` (default `http://localhost:11434/api/generate`).
   - `OLLAMA_MODEL` (default `phi3:mini`).
4) Ensure Ollama is installed and running and the chosen model is available.

## TODO

Flavor Signal currently runs on a local setup with an RTX 3070. While this setup works well for experimentation and correctness, local LLM inference introduces noticeable latency during summarization. Reducing end-to-end response time is a key focus going forward.

Planned optimizations and architectural improvements include:

- **Batch summarization in a single LLM call**  
  Instead of calling the summarization model once per restaurant, build a single prompt that includes top review snippets for all restaurants and ask the model to return structured (JSON) summaries for each place.  
  This reduces *N* LLM calls to **1**, and is expected to provide the largest performance improvement.

- **Progressive / streaming results (UX-focused change)**  
  Move toward a progressive response architecture:
  - Immediately return the list of restaurants with mention counts (fast).
  - Stream dish-level summaries as they complete using Server-Sent Events (SSE) or WebSockets.
  
  Even if total processing time remains ~10–12 seconds, this approach dramatically improves perceived latency and user experience by delivering useful information within the first few seconds.

These changes aim to make Flavor Signal feel responsive and interactive while preserving the quality and interpretability of dish-level summaries.
