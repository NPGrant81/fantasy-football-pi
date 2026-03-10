import React, { useState, useEffect } from 'react';
// using the 2D-specific build avoids pulling in AFRAME/VR extras
// the module exports a default component, not a named one
import ForceGraph2D from 'react-force-graph-2d';
import { fetchCurrentUser } from '@api/commonApi';
import { fetchRivalryAnalytics } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';

// Visualizes head-to-head and trade relationships between managers in a league
const RivalryGraph = () => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const user = await fetchCurrentUser();
        const leagueId = user?.league_id;
        if (!leagueId) {
          setError('League not found');
          setLoading(false);
          return;
        }
        const payload = await fetchRivalryAnalytics(leagueId);
        const { nodes, edges } = payload || { nodes: [], edges: [] };
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
        setError(normalizeApiError(err, 'Failed to load rivalry data'));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <LoadingState message="Loading rivalry graph..." />;
  }
  if (error) {
    return <ErrorState message={error} />;
  }
  if (graphData.nodes.length === 0) {
    return <EmptyState message="No rivalry data available." />;
  }

  return (
    <div
      className="md:h-96"
      style={{ width: '100%', height: '500px', background: '#222' }}
    >
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
