// frontend/src/utils/api.js
const _raw = import.meta.env.VITE_API_URL;
const BASE_URL = _raw ? _raw.replace(/\/$/, "") + "/api" : "/api";

export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export function streamChat(sessionId, messages, settings, onEvent, onError) {
  const controller = new AbortController();
  fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId, // <-- Required for database saving
      messages,
      model: settings.model,
      max_tokens: settings.maxTokens,
      temperature: settings.temperature,
      enable_thinking: settings.enableThinking,
      enable_web_search: settings.enableWebSearch,
      enable_web_reader: settings.enableWebReader,
    }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) { onError(new Error(await res.text() || "Failed")); return; }
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
            try { onEvent(JSON.parse(raw)); } catch {}
          }
        }
      }
    })
    .catch((err) => { if (err.name !== "AbortError") onError(err); });
  return () => controller.abort();
}
