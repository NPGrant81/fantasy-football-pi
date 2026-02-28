import React, { useState, useEffect } from 'react';
import { ForceGraph2D } from 'react-force-graph';
import apiClient from '@api/client';

// Visualizes head-to-head and trade relationships between managers in a league
const RivalryGraph = () => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        // convert edges to force-graph links
        const links = edges.map((e) => ({
          source: e.source,
          target: e.target,
          games: e.games,
          trades: e.trades,
        }));
        setGraphData({ nodes, links });
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
    <div style={{ width: '100%', height: '500px', background: '#222' }}>
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="label"
        linkWidth={(link) => Math.max(1, Math.log1p(link.games))}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const label = node.label || node.id;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          ctx.fillStyle = '#ffffff';
          ctx.fillText(label, node.x + 6, node.y + 3);
        }}
      />
    </div>
  );
};

export default RivalryGraph;
