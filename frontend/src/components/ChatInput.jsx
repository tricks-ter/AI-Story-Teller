import { useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";

export default function ChatInput({ value, onChange, onSend, onStop, isStreaming, disabled }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, [value]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && value.trim()) onSend();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2">
      <div
        className="
          flex items-end gap-2 bg-gray-800 border border-gray-700
          rounded-2xl px-4 py-3
          focus-within:border-brand-500 transition-colors duration-200
        "
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message… (Shift+Enter for newline)"
          rows={1}
          disabled={disabled}
          className="
            flex-1 bg-transparent text-gray-100 placeholder-gray-500
            text-sm resize-none outline-none leading-relaxed
            max-h-40 overflow-y-auto
          "
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="
              flex-shrink-0 w-9 h-9 rounded-xl
              bg-red-500/20 hover:bg-red-500/40
              text-red-400 hover:text-red-300
              flex items-center justify-center
              transition-colors duration-150
            "
            title="Stop generation"
          >
            <Square size={16} />
          </button>
        ) : (
          <button
            onClick={onSend}
            disabled={!value.trim() || disabled}
            className="
              flex-shrink-0 w-9 h-9 rounded-xl
              bg-brand-600 hover:bg-brand-700
              disabled:opacity-40 disabled:cursor-not-allowed
              text-white flex items-center justify-center
              transition-colors duration-150
            "
            title="Send (Enter)"
          >
            <Send size={16} />
          </button>
        )}
      </div>
      <p className="text-xs text-gray-600 text-center mt-2">
        GLM-4.7-Flash may make mistakes. Verify important information.
      </p>
    </div>
  );
}
