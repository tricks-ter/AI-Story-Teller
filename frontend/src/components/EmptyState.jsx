import { Bot, Zap, Brain, Code2, Lightbulb, ArrowRight } from "lucide-react";

const suggestions = [
  { icon: Lightbulb, text: "Explain quantum computing in simple terms" },
  { icon: Code2, text: "Write a Python function to parse JSON" },
  { icon: Brain, text: "What are the latest trends in AI?" },
  { icon: Zap, text: "Help me write a marketing email" },
];

export default function EmptyState({ onSuggestion }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-6 animate-fade-in">
      <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center mb-4 shadow-lg shadow-brand-500/20">
        <Bot size={28} className="text-white" />
      </div>

      <h1 className="text-xl sm:text-2xl font-bold text-white mb-2 text-center">
        How can I help you?
      </h1>
      <p className="text-gray-400 text-sm text-center mb-6 max-w-xs sm:max-w-md">
        Tap a suggestion to send instantly, or type your own message below.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 w-full max-w-2xl">
        {suggestions.map(({ icon: Icon, text }) => (
          <button
            key={text}
            onClick={() => onSuggestion(text)}
            className="flex items-center gap-3 p-4 rounded-xl text-left bg-gray-800/70 hover:bg-gray-800 active:bg-gray-700 border border-gray-700 hover:border-brand-500/50 text-sm text-gray-300 hover:text-white transition-colors duration-150 group min-h-[60px] touch-manipulation"
          >
            <Icon size={18} className="text-brand-400 flex-shrink-0 group-hover:text-brand-300" />
            <span className="flex-1 leading-snug">{text}</span>
            <ArrowRight size={13} className="text-gray-600 group-hover:text-brand-400 flex-shrink-0 transition-colors" />
          </button>
        ))}
      </div>
    </div>
  );
}
