import React, { useState, useEffect, useRef } from 'react';
// using the 2D-specific build avoids pulling in AFRAME/VR extras
// the module exports a default component, not a named one
import ForceGraph2D from 'react-force-graph-2d';
import apiClient from '@api/client';

// Palette for deterministic node coloring by index
const NODE_COLORS = [
  '#4a90e2', '#e24a4a', '#4ae27a', '#e2c44a',
  '#c44ae2', '#4ae2e2', '#e2784a', '#784ae2',
];

// Visualizes head-to-head and trade relationships between managers in a league
const RivalryGraph = () => {
  const containerRef = useRef(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [width, setWidth] = useState(600);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Track container width for responsive sizing
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setWidth(entry.contentRect.width || 600);
      }
    });
    observer.observe(containerRef.current);
    // Set initial width
    setWidth(containerRef.current.offsetWidth || 600);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    async function load() {
      try {
        const userRes = await apiClient.get('/auth/me');
        const leagueId = userRes.data?.league_id;
        if (!leagueId) {
          setError('League not found');
          setLoading(false);
          return;
        }
        const res = await apiClient.get(
          `/analytics/league/${leagueId}/rivalry`
        );
        const { nodes, edges } = res.data || { nodes: [], edges: [] };
        // assign a stable color to each node by index
        const coloredNodes = nodes.map((n, i) => ({
          ...n,
          color: NODE_COLORS[i % NODE_COLORS.length],
        }));
        // convert edges to force-graph links
        // wins keys are strings in JSON (Python serialises int dict keys as strings)
        const links = edges.map((e) => ({
          source: e.source,
          target: e.target,
          games: e.games,
          trades: e.trades,
          wins: e.wins || {},
        }));
        setGraphData({ nodes: coloredNodes, links });
      } catch (err) {
        console.error(err);
        setError(err.message || 'Failed to load rivalry data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <p>Loading rivalry graph...</p>;
  }
  if (error) {
    return <p className="text-red-500">Error: {error}</p>;
  }
  if (graphData.nodes.length === 0) {
    return <p>No rivalry data available.</p>;
  }

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '500px', background: '#222' }}
    >
      <ForceGraph2D
        graphData={graphData}
        width={width}
        height={500}
        nodeLabel="label"
        nodeAutoColorBy="id"
        linkWidth={(link) => Math.max(1, Math.log1p(link.games))}
        linkLabel={(link) =>
          `Games: ${link.games}, Trades: ${link.trades}`
        }
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.label || String(node.id);
          const fontSize = 12 / globalScale;
          const r = 6;

          // draw node circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = node.color || '#4a90e2';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5 / globalScale;
          ctx.stroke();

          // draw label to the right of the circle
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.fillStyle = '#ffffff';
          ctx.fillText(label, node.x + r + 2, node.y + fontSize / 4);
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          // paint hit-test area matching the circle
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI);
          ctx.fill();
        }}
      />
    </div>
  );
};

export default RivalryGraph;
