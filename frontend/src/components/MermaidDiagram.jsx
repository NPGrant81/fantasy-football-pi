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

let diagramIdCounter = 0;

export default function MermaidDiagram({ chart }) {
  const containerRef = useRef(null);
  const [error, setError] = useState(null);
  const [svg, setSvg] = useState('');

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setSvg('');

    getMermaid()
      .then(async (mermaid) => {
        const id = `mermaid-diagram-${++diagramIdCounter}`;
        const { svg: renderedSvg } = await mermaid.render(id, chart);
        if (!cancelled) {
          setSvg(renderedSvg);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.message || 'Invalid diagram syntax');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-red-500 bg-red-900/20 p-3 text-xs text-red-300"
      >
        <span className="font-semibold">Diagram error: </span>
        {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="text-xs text-slate-400 italic py-2">
        Rendering diagram…
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="my-2 overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
