import { PlusCircle, MessageSquare, Trash2, Bot } from "lucide-react";

function formatDate(isoString) {
  const d = new Date(isoString);
  const now = new Date();
  const diff = now - d;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

export default function Sidebar({ sessions, activeId, onSelect, onCreate, onDelete, isOpen }) {
  return (
    <aside
      className={`
        flex flex-col bg-gray-950 border-r border-gray-800
        w-72 flex-shrink-0 transition-all duration-300
        ${isOpen ? "translate-x-0" : "-translate-x-full"}
        fixed inset-y-0 left-0 z-30
        md:relative md:translate-x-0
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-600">
          <Bot size={18} className="text-white" />
        </div>
        <span className="text-white font-semibold text-lg tracking-tight">GLM Chat</span>
      </div>

      {/* New Chat Button */}
      <div className="px-3 py-3">
        <button
          onClick={onCreate}
          className="
            flex items-center gap-2 w-full px-4 py-2.5
            rounded-xl bg-brand-600 hover:bg-brand-700
            text-white text-sm font-medium
            transition-colors duration-150
          "
        >
          <PlusCircle size={16} />
          New Chat
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-1">
        {sessions.length === 0 && (
          <p className="text-gray-500 text-xs text-center mt-8">No chats yet. Start one!</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.session_id}
            onClick={() => onSelect(s.session_id)}
            className={`
              group flex items-start gap-2 px-3 py-2.5 rounded-xl cursor-pointer
              transition-colors duration-150
              ${activeId === s.session_id
                ? "bg-brand-600/20 border border-brand-500/30"
                : "hover:bg-gray-800 border border-transparent"
              }
            `}
          >
            <MessageSquare
              size={15}
              className={`mt-0.5 flex-shrink-0 ${activeId === s.session_id ? "text-brand-400" : "text-gray-500"}`}
            />
            <div className="flex-1 min-w-0">
              <p className={`text-sm truncate ${activeId === s.session_id ? "text-white" : "text-gray-300"}`}>
                {s.title || "New Chat"}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {s.message_count} msg{s.message_count !== 1 ? "s" : ""} · {formatDate(s.created_at)}
              </p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(s.session_id); }}
              className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-all flex-shrink-0"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800">
        <p className="text-xs text-gray-600 text-center">Powered by GLM-4.7-Flash · Z.AI</p>
      </div>
    </aside>
  );
}
