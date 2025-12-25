"use client";

import { useMemo, useState } from "react";
import styles from "./page.module.css";
import { analyze, type AnalyzeResp } from "@/lib/api";

function Stars({ rating }: { rating?: number | null }) {
  const r = typeof rating === "number" ? Math.max(0, Math.min(5, rating)) : null;
  const full = r ? Math.round(r) : 0;

  return (
    <div className={styles.starsRow}>
      <div className={styles.stars} aria-label={r ? `Rating ${r.toFixed(1)} out of 5` : "No rating"}>
        {Array.from({ length: 5 }).map((_, i) => (
          <span key={i} className={i < full ? styles.starOn : styles.starOff} aria-hidden>
            ★
          </span>
        ))}
      </div>
      <span className={styles.starText}>{r ? r.toFixed(1) : "—"}</span>
    </div>
  );
}

export default function Home() {
  const [location, setLocation] = useState("");
  const [item, setItem] = useState("");
  const [data, setData] = useState<AnalyzeResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const canSubmit = useMemo(
    () => location.trim().length > 0 && item.trim().length > 0,
    [location, item]
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || loading) return;

    setErr(null);
    setData(null);
    setLoading(true);

    try {
      const resp = await analyze({ location: location.trim(), item: item.trim() });
      setData(resp);
    } catch (ex: any) {
      setErr(ex?.message ?? "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        {/* Brand / hero */}
        <header className={styles.hero}>
          <div className={styles.brandBlock}>
            <div className={styles.brandName}>
              <span className={styles.brandStrong}>Flavor</span>{" "}
              <span className={styles.brandLight}>Signal</span>
            </div>

            <div className={styles.tagline}>Cut through the noise</div>

            <p className={styles.heroText}>
              Looking for a specific dish nearby? Flavor Signal shows you what people
              actually say about that item — not the restaurant in general. Get clear,
              dish-specific summaries so you can decide what to order without digging
              through endless reviews.
            </p>

            <p className={styles.heroSubtle}>
              No scrolling. No guesswork. Just what you're looking for.
            </p>
          </div>

        </header>

        {/* Search panel */}
        <section className={styles.panel}>
          <form onSubmit={onSubmit} className={styles.form}>
            <div className={styles.fieldWrap}>
              <input
                id="location"
                className={styles.floatInput}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder=" "     // IMPORTANT: a single space, enables :placeholder-shown trick
                autoComplete="off"
              />
              <label className={styles.floatLabel} htmlFor="location">
                Location (e.g., Arlington, VA)
              </label>
            </div>

            <div className={styles.fieldWrap}>
              <input
                id="item"
                className={styles.floatInput}
                value={item}
                onChange={(e) => setItem(e.target.value)}
                placeholder=" "
                autoComplete="off"
              />
              <label className={styles.floatLabel} htmlFor="item">
                Food item (e.g., hot chocolate)
              </label>
            </div>


            <button className={styles.button} type="submit" disabled={!canSubmit || loading}>
              {loading ? "Analyzing…" : "Search"}
            </button>
          </form>

          {err && (
            <div className={styles.errorBox}>
              <div className={styles.errorTitle}>Couldn’t fetch results</div>
              <div className={styles.errorText}>{err}</div>
            </div>
          )}
        </section>

        {/* Results */}
        <section className={styles.results}>
          {loading && (
            <div className={styles.grid}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className={styles.skeletonCard}>
                  <div className={styles.skelTopRow}>
                    <div className={styles.skelLineWide} />
                    <div className={styles.skelPill} />
                  </div>
                  <div className={styles.skelLineNarrow} />
                  <div className={styles.skelBlock} />
                </div>
              ))}
            </div>
          )}

          {!loading && data && (
            <>
              <div className={styles.resultsHeader}>
                <div className={styles.resultsTitle}>Results</div>
                <div className={styles.metaRow}>
                  <span className={styles.metaChip}>
                    <span className={styles.metaKey}>Location</span>
                    <span className={styles.metaVal}>{data.location}</span>
                  </span>
                  <span className={styles.metaChip}>
                    <span className={styles.metaKey}>Item</span>
                    <span className={styles.metaVal}>{data.item}</span>
                  </span>
                  <span className={styles.metaCount}>
                    {data.results.length} restaurant{data.results.length === 1 ? "" : "s"}
                  </span>
                </div>
              </div>

              {data.results.length === 0 ? (
                <div className={styles.empty}>No results returned.</div>
              ) : (
                <div className={styles.grid}>
                  {data.results.filter(r => r.mentions > 0).map((r, idx) => (
                    <article key={idx} className={styles.card}>
                      <div className={styles.cardTop}>
                        <div className={styles.cardLeft}>
                          <div className={styles.cardTitle}>{r.place.title}</div>
                          <Stars rating={r.place.rating ?? null} />
                        </div>

                        <div className={styles.cardRight}>
                          <div className={styles.pill}>
                            Mentions <span className={styles.pillStrong}>{r.mentions}</span>
                          </div>
                          <div className={styles.pillMuted}>
                            Fetched <span className={styles.pillStrong}>{r.reviews_fetched}</span>
                          </div>
                        </div>
                      </div>


                      <p className={styles.summary}>{r.summary}</p>

                      {typeof r.place.reviews_count === "number" && (
                        <p className={styles.small}>Place rating count: {r.place.reviews_count}</p>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        <footer className={styles.footer}>
          <span>Flavor Signal</span>
          <span className={styles.footerDot} aria-hidden />
          <span>Cut through the noise</span>
          <span className={styles.footerSpacer} />
          <span className={styles.footerAuthor}>Built by Aniket Konkar</span>
        </footer>

      </div>
    </main>
  );
}
