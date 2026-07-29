const KEY = "glm_chat_data";

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : { sessions: {} };
  } catch {
    return { sessions: {} };
  }
}

function persist(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    // localStorage might be full or unavailable (private browsing)
  }
}

export function listSessions() {
  const { sessions } = load();
  return Object.values(sessions).sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );
}

export function createSession() {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();
  const session = {
    session_id: id,
    created_at: now,
    title: "New Chat",
    messages: [],
  };
  const data = load();
  data.sessions[id] = session;
  persist(data);
  return session;
}

export function getSession(sessionId) {
  return load().sessions[sessionId] || null;
}

export function getMessages(sessionId) {
  return load().sessions[sessionId]?.messages ?? [];
}

export function appendMessage(sessionId, message) {
  const data = load();
  if (!data.sessions[sessionId]) return;
  data.sessions[sessionId].messages.push(message);
  persist(data);
}

export function updateSessionTitle(sessionId, title) {
  const data = load();
  if (!data.sessions[sessionId]) return;
  data.sessions[sessionId].title = title;
  persist(data);
}

export function deleteSession(sessionId) {
  const data = load();
  delete data.sessions[sessionId];
  persist(data);
}
