async function request(path, signal) {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), 12000);
  const abort = () => timeout.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) abort();
  try {
    const response = await fetch(`/api${path}`, { signal: timeout.signal });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = typeof body?.detail === "string" ? body.detail : "We couldn't complete this request. Please try again.";
      throw new Error(detail);
    }
    if (body === null) throw new Error("The API returned an unreadable response.");
    return body;
  } catch (error) {
    if (signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
    if (error.name === "AbortError") throw new Error("The server took too long. Please try again.", { cause: error });
    if (error instanceof TypeError) throw new Error("Can't reach the server. Check that the backend is running, then retry.", { cause: error });
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export const fetchHealth = (signal) => request("/health", signal);
export const fetchTowers = (signal) => request("/towers", signal);
export const fetchBoundary = (signal) => request("/boundary", signal);
export const fetchPrediction = (lat, lon, signal) => request(`/predict?${new URLSearchParams({ lat, lon })}`, signal);
