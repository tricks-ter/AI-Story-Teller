import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import EmptyState from "./EmptyState";

export default function ChatWindow({ messages, streamingMsg, isStreaming, onSuggestion }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMsg]);

  const hasMessages = messages.length > 0 || streamingMsg;

  return (
    <div className="flex-1 overflow-y-auto">
      {!hasMessages ? (
        <EmptyState onSuggestion={onSuggestion} />
      ) : (
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-8">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} isStreaming={false} />
          ))}

          {/* Streaming assistant message */}
          {streamingMsg && (
            <MessageBubble
              message={streamingMsg}
              isStreaming={isStreaming}
            />
          )}

          {/* Typing indicator while connecting */}
          {isStreaming && !streamingMsg && <TypingIndicator />}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
