import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import EmptyState from "./EmptyState";

export default function ChatWindow({
  messages,
  streamingMsg,
  isStreaming,
  statusText,
  onSuggestion,
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMsg, statusText]);

  const hasMessages = messages.length > 0 || streamingMsg;

  return (
    <div className="flex-1 overflow-y-auto overscroll-contain">
      {!hasMessages ? (
        <EmptyState onSuggestion={onSuggestion} />
      ) : (
        <div className="max-w-3xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-6 sm:space-y-8">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} isStreaming={false} />
          ))}

          {streamingMsg && (
            <MessageBubble message={streamingMsg} isStreaming={isStreaming} />
          )}

          {isStreaming && !streamingMsg && (
            <TypingIndicator statusText={statusText} />
          )}

          <div ref={bottomRef} className="h-1" />
        </div>
      )}
    </div>
  );
}
