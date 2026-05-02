import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import {
  fetchDraftValueAnalytics,
  resolveRows,
} from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
import { useTheme } from '../../hooks/useTheme';
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
  const { theme } = useTheme();
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  const isDark = theme === 'dark';
  const chartText = isDark ? '#cbd5e1' : '#334155';
  const chartTitle = isDark ? '#f8fafc' : '#0f172a';
  const chartGrid = isDark ? 'rgba(148, 163, 184, 0.18)' : 'rgba(100, 116, 139, 0.2)';

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
          color: chartText,
          font: {
            size: 14,
          },
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.97)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#cbd5e1' : '#334155',
        borderColor: isDark ? '#334155' : '#e2e8f0',
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
          color: chartTitle,
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: chartText,
        },
        grid: {
          color: chartGrid,
        },
        reverse: true,
      },
      y: {
        type: 'linear',
        title: {
          display: true,
          text: 'Projected Season Points',
          color: chartTitle,
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: chartText,
        },
        grid: {
          color: chartGrid,
        },
      },
    },
  };

  return (
    <div className="md:block h-[500px] rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900/40">
      <h3 className="mb-5 mt-0 text-center text-lg font-semibold text-slate-900 dark:text-slate-100">
        Draft Value Analysis
      </h3>
      <p className="mb-5 text-center text-sm text-slate-600 dark:text-slate-400">
        Higher points with later ADP indicate stronger draft value opportunities.
      </p>
      <Scatter data={{ datasets }} options={options} />
    </div>
  );
};

export default DraftValueBoard;
