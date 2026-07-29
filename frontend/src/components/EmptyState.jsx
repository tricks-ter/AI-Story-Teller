import { Bot, Zap, Brain, Code2, Lightbulb } from "lucide-react";

const suggestions = [
  { icon: Lightbulb, text: "Explain quantum computing in simple terms" },
  { icon: Code2, text: "Write a Python function to parse JSON" },
  { icon: Brain, text: "What are the latest trends in AI?" },
  { icon: Zap, text: "Help me write a marketing email" },
];

export default function EmptyState({ onSuggestion }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 animate-fade-in">
      {/* Logo */}
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center mb-6 shadow-lg shadow-brand-500/20">
        <Bot size={32} className="text-white" />
      </div>

      <h1 className="text-2xl font-bold text-white mb-2 text-center">How can I help you today?</h1>
      <p className="text-gray-400 text-sm text-center mb-10 max-w-md">
        I&apos;m powered by GLM-4.7-Flash with advanced reasoning. Ask me anything!
      </p>

      {/* Suggestion cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {suggestions.map(({ icon: Icon, text }) => (
          <button
            key={text}
            onClick={() => onSuggestion(text)}
            className="
              flex items-start gap-3 p-4 rounded-xl
              bg-gray-800/60 hover:bg-gray-800
              border border-gray-700 hover:border-brand-500/50
              text-left text-sm text-gray-300 hover:text-white
              transition-all duration-200 group
            "
          >
            <Icon size={18} className="text-brand-400 mt-0.5 flex-shrink-0 group-hover:text-brand-300" />
            <span>{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
