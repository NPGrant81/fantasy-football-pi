import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import {
  fetchDraftValueAnalytics,
  resolveRows,
} from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Scatter } from 'react-chartjs-2';

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

const POSITION_COLORS = {
  RB: {
    backgroundColor: 'rgba(255, 99, 132, 0.6)',
    borderColor: 'rgba(255, 99, 132, 1)',
  },
  WR: {
    backgroundColor: 'rgba(54, 162, 235, 0.6)',
    borderColor: 'rgba(54, 162, 235, 1)',
  },
  QB: {
    backgroundColor: 'rgba(75, 192, 192, 0.6)',
    borderColor: 'rgba(75, 192, 192, 1)',
  },
  TE: {
    backgroundColor: 'rgba(255, 206, 86, 0.6)',
    borderColor: 'rgba(255, 206, 86, 1)',
  },
};

const POSITION_LABELS = {
  RB: 'Running Backs',
  WR: 'Wide Receivers',
  QB: 'Quarterbacks',
  TE: 'Tight Ends',
};

const DraftValueBoard = () => {
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    const load = async () => {
      try {
        const user = await fetchCurrentUser();
        const leagueId = user?.league_id;
        if (!leagueId) {
          setError('League not found.');
          return;
        }

        const season = new Date().getFullYear();
        const payload = await fetchDraftValueAnalytics(leagueId, season, 80);
        setRows(resolveRows(payload));
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'Failed to load draft value data.'));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return <LoadingState message="Loading draft value analysis..." />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!Array.isArray(rows) || rows.length === 0) {
    return <EmptyState message="No draft value data available." />;
  }

  const supportedRows = rows.filter((row) =>
    Object.prototype.hasOwnProperty.call(POSITION_COLORS, String(row.position || '').toUpperCase())
  );

  const datasets = Object.keys(POSITION_COLORS).map((position) => {
    const color = POSITION_COLORS[position];
    return {
      label: POSITION_LABELS[position],
      data: supportedRows
        .filter((row) => String(row.position || '').toUpperCase() === position)
        .map((row) => ({
          x: Number(row.adp || 0),
          y: Number(row.projected_points || 0),
          playerName: row.player_name,
          valueScore: Number(row.value_score || 0),
        })),
      backgroundColor: color.backgroundColor,
      borderColor: color.borderColor,
      pointRadius: 8,
      pointHoverRadius: 12,
    };
  });

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#ffffff',
          font: {
            size: 14,
          },
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#4a90e2',
        borderWidth: 1,
        padding: 12,
        callbacks: {
          label(context) {
            const player = context.raw;
            return [
              `${player.playerName}`,
              `ADP: ${Number(player.x || 0).toFixed(1)}`,
              `Projected: ${Number(player.y || 0).toFixed(1)} pts`,
              `Value Score: ${Number(player.valueScore || 0).toFixed(3)}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        position: 'bottom',
        title: {
          display: true,
          text: 'Average Draft Position (ADP)',
          color: '#ffffff',
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: '#cccccc',
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        reverse: true,
      },
      y: {
        type: 'linear',
        title: {
          display: true,
          text: 'Projected Season Points',
          color: '#ffffff',
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: '#cccccc',
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
      },
    },
  };

  return (
    <div
      className="md:block"
      style={{
        height: '500px',
        padding: '20px',
        backgroundColor: '#2a2a2a',
        borderRadius: '8px',
      }}
    >
      <h3
        style={{
          color: '#ffffff',
          marginTop: 0,
          marginBottom: '20px',
          textAlign: 'center',
        }}
      >
        Draft Value Analysis
      </h3>
      <p
        style={{
          color: '#cccccc',
          fontSize: '14px',
          textAlign: 'center',
          marginBottom: '20px',
        }}
      >
        Higher points with later ADP indicate stronger draft value opportunities.
      </p>
      <Scatter data={{ datasets }} options={options} />
    </div>
  );
};

export default DraftValueBoard;
