import { useState } from "react";
import { Globe, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

export default function SourcesList({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 border border-gray-700/60 rounded-xl overflow-hidden bg-gray-900/40">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full px-3 py-2.5 text-xs text-gray-400 hover:bg-gray-800/60 transition-colors min-h-[40px] touch-manipulation"
      >
        <Globe size={13} className="text-brand-400 flex-shrink-0" />
        <span className="font-medium text-gray-300">
          {sources.length} web source{sources.length !== 1 ? "s" : ""}
        </span>
        {open ? (
          <ChevronUp size={12} className="ml-auto" />
        ) : (
          <ChevronDown size={12} className="ml-auto" />
        )}
      </button>

      {open && (
        <div className="divide-y divide-gray-800/60">
          {sources.map((s, i) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2 px-3 py-2.5 hover:bg-gray-800/60 transition-colors group"
            >
              <span className="text-[11px] text-gray-600 font-mono mt-0.5 w-4 flex-shrink-0">
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-300 group-hover:text-brand-400 truncate leading-snug">
                  {s.title || s.url}
                </p>
                {s.summary && (
                  <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2 leading-relaxed">
                    {s.summary}
                  </p>
                )}
                <p className="text-[10px] text-gray-600 mt-0.5 truncate">{s.url}</p>
              </div>
              <ExternalLink
                size={11}
                className="text-gray-600 group-hover:text-brand-400 flex-shrink-0 mt-0.5 transition-colors"
              />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
