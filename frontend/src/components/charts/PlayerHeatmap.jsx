import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import { fetchPlayerHeatmapAnalytics } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
import { useTheme } from '../../hooks/useTheme';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
  Legend,
  MatrixController,
  MatrixElement
);

const PlayerHeatmap = () => {
  const { theme } = useTheme();
  const [rows, setRows] = React.useState([]);
  const [weeks, setWeeks] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  const isDark = theme === 'dark';
  const chartText = isDark ? '#cbd5e1' : '#334155';

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
        const payload = (await fetchPlayerHeatmapAnalytics(leagueId, season, 8, 8)) || {};
        setRows(Array.isArray(payload.rows) ? payload.rows : []);
        setWeeks(Array.isArray(payload.week_labels) ? payload.week_labels : []);
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'Failed to load player heatmap data.'));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return <LoadingState message="Loading player heatmap..." />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!rows.length || !weeks.length) {
    return <EmptyState message="No player heatmap data available." />;
  }

  const players = rows.map((row) => row.player_name);
  const performanceData = [];

  rows.forEach((row, playerIndex) => {
    const weekly = Array.isArray(row.points_by_week) ? row.points_by_week : [];
    weekly.forEach((points, weekIndex) => {
      performanceData.push({ x: weekIndex, y: playerIndex, v: Number(points || 0) });
    });
  });

  const maxValue = performanceData.reduce((acc, item) => Math.max(acc, item.v), 0);

  const data = {
    datasets: [
      {
        label: 'Fantasy Points',
        data: performanceData,
        backgroundColor(context) {
          const value = context.dataset.data[context.dataIndex].v;
          const alpha = (maxValue > 0 ? value / maxValue : 0).toFixed(2);
          if (value >= 20) return `rgba(34, 197, 94, ${alpha})`;
          if (value >= 10) return `rgba(250, 204, 21, ${alpha})`;
          return `rgba(239, 68, 68, ${Math.max(0.2, Number(alpha))})`;
        },
        borderColor: 'rgba(255, 255, 255, 0.2)',
        borderWidth: 1,
        width: ({ chart }) => (chart.chartArea || {}).width / weeks.length - 1,
        height: ({ chart }) => (chart.chartArea || {}).height / players.length - 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.97)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#cbd5e1' : '#334155',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        borderWidth: 1,
        padding: 12,
        callbacks: {
          title() {
            return 'Player Performance';
          },
          label(context) {
            const point = context.dataset.data[context.dataIndex];
            return [
              `Player: ${players[point.y]}`,
              `${weeks[point.x]}`,
              `Points: ${point.v.toFixed(1)}`,
            ];
          },
        },
      },
    },
    scales: {
      x: {
        type: 'category',
        labels: weeks,
        ticks: {
          color: chartText,
        },
        grid: {
          display: false,
        },
      },
      y: {
        type: 'category',
        labels: players,
        offset: true,
        ticks: {
          color: chartText,
        },
        grid: {
          display: false,
        },
      },
    },
  };

  return (
    <div className="md:block h-[500px] rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900/40">
      <h3 className="mb-2.5 mt-0 text-center text-lg font-semibold text-slate-900 dark:text-slate-100">
        Player Performance Heatmap
      </h3>
      <p className="mb-5 text-center text-sm text-slate-600 dark:text-slate-400">
        Weekly fantasy scoring by player under the active league scoring profile.
      </p>
      <Chart type="matrix" data={data} options={options} />
    </div>
  );
};

export default PlayerHeatmap;
