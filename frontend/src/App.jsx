import { useState, useEffect, useCallback, useRef } from "react";
import { Menu, X, AlertCircle } from "lucide-react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import { streamChat } from "./utils/api";
import {
  listSessions,
  createSession,
  getMessages,
  appendMessage,
  updateSessionTitle,
  deleteSession,
} from "./utils/storage";

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

  useEffect(() => {
    setSessions(listSessions());
  }, []);

  const refreshSessions = () => setSessions(listSessions());

  const handleSelectSession = (sessionId) => {
    setActiveSessionId(sessionId);
    setMessages(getMessages(sessionId));
    setStreamingMsg(null);
    setError(null);
    setSidebarOpen(false);
  };

  const handleNewChat = () => {
    const session = createSession();
    refreshSessions();
    setActiveSessionId(session.session_id);
    setMessages([]);
    setStreamingMsg(null);
    setError(null);
    setSidebarOpen(false);
  };

  const handleDeleteSession = (sessionId) => {
    deleteSession(sessionId);
    refreshSessions();
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
      setMessages([]);
      setStreamingMsg(null);
    }
  };

  /**
   * Core send logic — accepts a text string directly so both the input
   * submit button AND the suggestion cards share identical behaviour.
   */
  const sendMessage = useCallback(
    (text) => {
      const msg = typeof text === "string" ? text.trim() : "";
      if (!msg || isStreaming) return;

      setInputValue("");
      setError(null);
      setIsStreaming(true);
      setStreamingMsg(null);

      // Ensure a session exists
      let sessionId = activeSessionId;
      if (!sessionId) {
        const session = createSession();
        sessionId = session.session_id;
        setActiveSessionId(sessionId);
        refreshSessions();
      }

      const userMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: msg,
        timestamp: new Date().toISOString(),
      };

      appendMessage(sessionId, userMessage);
      setMessages((prev) => [...prev, userMessage]);

      // Auto-title on first message
      const saved = getMessages(sessionId);
      if (saved.length === 1) {
        updateSessionTitle(sessionId, msg.length > 50 ? msg.slice(0, 50) + "…" : msg);
        refreshSessions();
      }

      // Build history to send (role + content only)
      const history = getMessages(sessionId).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const assistantId = `assistant-${Date.now()}`;
      let assistantContent = "";
      let assistantThinking = "";

      const cancel = streamChat(
        history,
        (event) => {
          switch (event.type) {
            case "status":
              // Server keepalive / connection confirmed — no UI change needed
              break;

            case "thinking": {
              assistantThinking += event.content;
              setStreamingMsg((prev) => ({
                ...(prev ?? {}),
                id: assistantId,
                role: "assistant",
                content: assistantContent,
                streamingThinking: assistantThinking,
                timestamp: new Date().toISOString(),
              }));
              break;
            }

            case "content": {
              assistantContent += event.content;
              setStreamingMsg((prev) => ({
                ...(prev ?? {}),
                id: assistantId,
                role: "assistant",
                content: assistantContent,
                timestamp: new Date().toISOString(),
              }));
              break;
            }

            case "error": {
              setError(event.message || "An error occurred. Please try again.");
              setIsStreaming(false);
              setStreamingMsg(null);
              break;
            }

            case "done": {
              const finalMsg = {
                id: assistantId,
                role: "assistant",
                content: assistantContent,
                thinking: assistantThinking || undefined,
                timestamp: new Date().toISOString(),
              };
              appendMessage(sessionId, finalMsg);
              setMessages((prev) => [...prev, finalMsg]);
              setStreamingMsg(null);
              setIsStreaming(false);
              refreshSessions();
              break;
            }

            default:
              break;
          }
        },
        (err) => {
          setError(err.message || "Connection error — please try again.");
          setIsStreaming(false);
          setStreamingMsg(null);
        }
      );

      stopRef.current = cancel;
    },
    [isStreaming, activeSessionId]
  );

  // Bound to the Send button / Enter key in ChatInput
  const handleSend = useCallback(() => {
    sendMessage(inputValue);
  }, [inputValue, sendMessage]);

  // Clicking a suggestion card immediately sends that text
  const handleSuggestion = useCallback(
    (text) => {
      sendMessage(text);
    },
    [sendMessage]
  );

  const handleStop = () => {
    if (stopRef.current) {
      stopRef.current();
      stopRef.current = null;
    }
    if (streamingMsg) {
      const stopped = {
        ...streamingMsg,
        content: (streamingMsg.content || "") + " *(generation stopped)*",
        thinking: streamingMsg.streamingThinking || undefined,
        streamingThinking: undefined,
      };
      appendMessage(activeSessionId, stopped);
      setMessages((prev) => [...prev, stopped]);
    }
    setStreamingMsg(null);
    setIsStreaming(false);
  };

  const activeTitle =
    sessions.find((s) => s.session_id === activeSessionId)?.title ||
    "GLM-4.7-Flash";

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100 overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        sessions={sessions}
        activeId={activeSessionId}
        onSelect={handleSelectSession}
        onCreate={handleNewChat}
        onDelete={handleDeleteSession}
        isOpen={sidebarOpen}
      />

      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className="md:hidden p-2 rounded-lg hover:bg-gray-800 text-gray-400"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-white truncate">{activeTitle}</h2>
            <p className="text-xs text-gray-500">Advanced reasoning model</p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-xs text-gray-400">Online</span>
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-2.5 bg-red-500/10 border-b border-red-500/20 text-red-400 text-sm animate-fade-in">
            <AlertCircle size={15} className="flex-shrink-0" />
            <span className="flex-1">{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-300 ml-2"
            >
              <X size={14} />
            </button>
          </div>
        )}

        <ChatWindow
          messages={messages}
          streamingMsg={streamingMsg}
          isStreaming={isStreaming}
          onSuggestion={handleSuggestion}
        />

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
