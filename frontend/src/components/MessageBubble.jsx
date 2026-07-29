import { useState } from "react";
import { Bot, User, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded-md hover:bg-gray-700/60 text-gray-500 hover:text-gray-300 transition-colors"
      title="Copy message"
    >
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
    </button>
  );
}

function ThinkingBlock({ content }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-3 border border-brand-500/20 rounded-xl overflow-hidden bg-brand-950/30">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs text-brand-400 hover:bg-brand-500/10 transition-colors"
      >
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        <span className="font-medium">Thinking process</span>
        <span className="text-brand-500/60 ml-auto">{content.length} chars</span>
      </button>
      {open && (
        <div className="px-3 pb-3">
          <p className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">{content}</p>
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({ message, isStreaming }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`
        flex gap-3 animate-slide-up
        ${isUser ? "flex-row-reverse" : "flex-row"}
      `}
    >
      {/* Avatar */}
      <div
        className={`
          flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center
          ${isUser ? "bg-brand-600" : "bg-gray-700"}
        `}
      >
        {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[80%] flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`
            relative group rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? "bg-brand-600 text-white rounded-tr-sm"
              : "bg-gray-800 text-gray-100 rounded-tl-sm"
            }
          `}
        >
          {/* Thinking block (assistant only) */}
          {!isUser && message.thinking && <ThinkingBlock content={message.thinking} />}

          {/* Streaming thinking block */}
          {!isUser && message.streamingThinking && (
            <ThinkingBlock content={message.streamingThinking} />
          )}

          {/* Message content */}
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  code: ({ inline, children }) =>
                    inline ? (
                      <code className="bg-gray-700 px-1 py-0.5 rounded text-brand-300 text-xs">{children}</code>
                    ) : (
                      <code className="block bg-gray-900 text-green-300 p-3 rounded-lg text-xs overflow-x-auto my-2 whitespace-pre">
                        {children}
                      </code>
                    ),
                  pre: ({ children }) => <>{children}</>,
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-400 underline">
                      {children}
                    </a>
                  ),
                  ul: ({ children }) => <ul className="list-disc pl-4 my-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-4 my-1">{children}</ol>,
                  li: ({ children }) => <li className="my-0.5">{children}</li>,
                  h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-1">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-base font-semibold mt-2 mb-1">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-brand-500 pl-3 italic text-gray-400 my-2">
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {message.content || ""}
              </ReactMarkdown>
            </div>
          )}

          {/* Streaming cursor */}
          {isStreaming && !isUser && (
            <span className="inline-block w-0.5 h-4 bg-brand-400 animate-pulse ml-0.5 align-middle" />
          )}

          {/* Copy button */}
          {!isStreaming && (
            <div className={`absolute -bottom-7 ${isUser ? "left-0" : "right-0"} opacity-0 group-hover:opacity-100 transition-opacity`}>
              <CopyButton text={message.content} />
            </div>
          )}
        </div>

        {/* Timestamp */}
        {message.timestamp && (
          <p className="text-xs text-gray-600 px-1">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        )}
      </div>
    </div>
  );
}
