// On Vercel (same-domain) VITE_API_URL is not set → BASE_URL = "/api".
// For an external backend (e.g. Render), set VITE_API_URL to the server root
// (without trailing slash). The "/api" segment is appended automatically.
const _rawBase = import.meta.env.VITE_API_URL;
const BASE_URL = _rawBase ? _rawBase.replace(/\/$/, "") + "/api" : "/api";

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

/**
 * Open a streaming chat request.
 * @param {Array<{role:string, content:string}>} messages - Full conversation history
 *        including the new user message as the last item.
 * @param {(event: object) => void} onEvent  - Called for each SSE event.
 * @param {(err: Error) => void}    onError  - Called on network/stream errors.
 * @returns {() => void} cancel - Call to abort the stream.
 */
export function streamChat(messages, onEvent, onError) {
  const controller = new AbortController();

  fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.text();
        onError(new Error(err || "Stream request failed"));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const raw = line.slice(6).trim();
            if (!raw) continue;
            try {
              onEvent(JSON.parse(raw));
            } catch {
              // skip malformed frames
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") onError(err);
    });

  return () => controller.abort();
}
