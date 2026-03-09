/* ignore-breakpoints */
import { useEffect, useRef, useState } from 'react';

let mermaidLoaded = false;
let mermaidInstance = null;

async function getMermaid() {
  if (mermaidInstance) return mermaidInstance;
  const mod = await import('mermaid');
  mermaidInstance = mod.default;
  if (!mermaidLoaded) {
    mermaidInstance.initialize({ startOnLoad: false, securityLevel: 'strict' });
    mermaidLoaded = true;
  }
  return mermaidInstance;
}

export default function MermaidDiagram({ chart }) {
  const containerRef = useRef(null);
  // resultByChart maps chart string -> { svg } | { error }
  // A missing entry means the chart is still rendering (loading state)
  const [resultByChart, setResultByChart] = useState({});

  useEffect(() => {
    let cancelled = false;

    getMermaid()
      .then(async (mermaid) => {
        const id = `mermaid-diagram-${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
        const { svg: renderedSvg } = await mermaid.render(id, chart);
        if (!cancelled) {
          setResultByChart((prev) => ({ ...prev, [chart]: { svg: renderedSvg } }));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setResultByChart((prev) => ({
            ...prev,
            [chart]: { error: err?.message || 'Invalid diagram syntax' },
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chart]);

  const result = resultByChart[chart];

  if (!result) {
    return (
      <div className="text-xs text-slate-400 italic py-2">
        Rendering diagram…
      </div>
    );
  }

  if (result.error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-red-500 bg-red-900/20 p-3 text-xs text-red-300"
      >
        <span className="font-semibold">Diagram error: </span>
        {result.error}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="my-2 overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: result.svg }}
    />
  );
}
