export type AnalyzeReq = {
  location: string;
  item: string;
};

export type Place = {
  title: string;
  rating?: number | null;
  reviews_count?: number | null;
};

export type AnalyzeResult = {
  place: Place;
  reviews_fetched: number;
  mentions: number;
  summary: string;
};

export type AnalyzeResp = {
  location: string;
  item: string;
  results: AnalyzeResult[];
};

export async function analyze(payload: AnalyzeReq): Promise<AnalyzeResp> {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

  const res = await fetch(`${base}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error (${res.status}): ${text || res.statusText}`);
  }

  return res.json();
}
