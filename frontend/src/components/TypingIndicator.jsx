import { Bot } from "lucide-react";

export default function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-gray-700 flex items-center justify-center">
        <Bot size={16} className="text-white" />
      </div>
      <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1">
        <span className="typing-dot w-2 h-2 rounded-full bg-brand-400" />
        <span className="typing-dot w-2 h-2 rounded-full bg-brand-400" />
        <span className="typing-dot w-2 h-2 rounded-full bg-brand-400" />
      </div>
    </div>
  );
}
