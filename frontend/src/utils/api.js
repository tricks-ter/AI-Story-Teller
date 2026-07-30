const _raw = import.meta.env.VITE_API_URL;
const BASE_URL = _raw ? _raw.replace(/\/$/, "") + "/api" : "/api";

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

/**
 * Open a streaming chat request.
 * @param {Array<{role,content}>} messages  Full history incl. the new user message.
 * @param {object}               settings   model, maxTokens, temperature, enableThinking
 * @param {Function}             onEvent    Called for each parsed SSE event object.
 * @param {Function}             onError    Called on network-level errors.
 * @returns {Function} cancel — call to abort the stream.
 */
export function streamChat(messages, settings, onEvent, onError) {
  const controller = new AbortController();

  fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages,
      model: settings.model,
      max_tokens: settings.maxTokens,
      temperature: settings.temperature,
      enable_thinking: settings.enableThinking,
    }),
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
