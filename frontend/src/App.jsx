import { useState, useEffect, useCallback, useRef } from "react";
import { Menu, X, AlertCircle } from "lucide-react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import { createSession, listSessions, getMessages, deleteSession, streamChat } from "./utils/api";

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMsg, setStreamingMsg] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState(null);
  const stopRef = useRef(null);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const data = await listSessions();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    }
  };

  const handleSelectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    setSidebarOpen(false);
    setStreamingMsg(null);
    setError(null);
    try {
      const data = await getMessages(sessionId);
      setMessages(data.messages || []);
    } catch (err) {
      setError("Failed to load messages: " + err.message);
    }
  };

  const handleNewChat = async () => {
    try {
      const session = await createSession();
      setSessions((prev) => [
        { session_id: session.session_id, created_at: session.created_at, title: "New Chat", message_count: 0 },
        ...prev,
      ]);
      setActiveSessionId(session.session_id);
      setMessages([]);
      setStreamingMsg(null);
      setError(null);
      setSidebarOpen(false);
    } catch (err) {
      setError("Failed to create session: " + err.message);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
        setStreamingMsg(null);
      }
    } catch (err) {
      setError("Failed to delete session: " + err.message);
    }
  };

  const handleSend = useCallback(async () => {
    const msg = inputValue.trim();
    if (!msg || isStreaming) return;

    setInputValue("");
    setError(null);
    setIsStreaming(true);
    setStreamingMsg(null);

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: msg,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    let resolvedSessionId = activeSessionId;
    let assistantContent = "";
    let assistantThinking = "";
    const assistantId = `assistant-${Date.now()}`;

    const cancel = streamChat(
      resolvedSessionId,
      msg,
      (event) => {
        switch (event.type) {
          case "session_id":
            resolvedSessionId = event.session_id;
            setActiveSessionId(event.session_id);
            break;

          case "thinking":
            assistantThinking += event.content;
            setStreamingMsg((prev) => ({
              id: assistantId,
              role: "assistant",
              content: assistantContent,
              streamingThinking: assistantThinking,
              timestamp: new Date().toISOString(),
              ...(prev || {}),
              streamingThinking: assistantThinking,
            }));
            break;

          case "content":
            assistantContent += event.content;
            setStreamingMsg({
              id: assistantId,
              role: "assistant",
              content: assistantContent,
              streamingThinking: assistantThinking || undefined,
              timestamp: new Date().toISOString(),
            });
            break;

          case "error":
            setError(event.message || "An error occurred");
            setIsStreaming(false);
            setStreamingMsg(null);
            break;

          case "done":
            // Finalize the streaming message
            const finalMsg = {
              id: assistantId,
              role: "assistant",
              content: assistantContent,
              thinking: assistantThinking || undefined,
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, finalMsg]);
            setStreamingMsg(null);
            setIsStreaming(false);

            // Update session list
            loadSessions();
            break;
        }
      },
      (err) => {
        setError(err.message || "Connection error");
        setIsStreaming(false);
        setStreamingMsg(null);
      }
    );

    stopRef.current = cancel;
  }, [inputValue, isStreaming, activeSessionId]);

  const handleStop = () => {
    if (stopRef.current) {
      stopRef.current();
      stopRef.current = null;
    }
    if (streamingMsg) {
      const finalMsg = {
        ...streamingMsg,
        content: (streamingMsg.content || "") + " *(generation stopped)*",
        thinking: streamingMsg.streamingThinking,
        streamingThinking: undefined,
      };
      setMessages((prev) => [...prev, finalMsg]);
    }
    setStreamingMsg(null);
    setIsStreaming(false);
  };

  const handleSuggestion = (text) => {
    setInputValue(text);
  };

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Overlay for mobile sidebar */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeId={activeSessionId}
        onSelect={handleSelectSession}
        onCreate={handleNewChat}
        onDelete={handleDeleteSession}
        isOpen={sidebarOpen}
      />

      {/* Main Area */}
      <div className="flex flex-col flex-1 min-w-0 md:ml-0">
        {/* Top Bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="md:hidden p-2 rounded-lg hover:bg-gray-800 text-gray-400"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-white truncate">
              {sessions.find((s) => s.session_id === activeSessionId)?.title || "GLM-4.7-Flash"}
            </h2>
            <p className="text-xs text-gray-500">Advanced reasoning model</p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-gray-400">Online</span>
          </div>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-red-400 text-sm animate-fade-in">
            <AlertCircle size={15} />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300">
              <X size={14} />
            </button>
          </div>
        )}

        {/* Chat */}
        <ChatWindow
          messages={messages}
          streamingMsg={streamingMsg}
          isStreaming={isStreaming}
          onSuggestion={handleSuggestion}
        />

        {/* Input */}
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          disabled={false}
        />
      </div>
    </div>
  );
}
