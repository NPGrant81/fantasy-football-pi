// Manager trend analysis line chart backed by analytics API weekly stats.

import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import { fetchManagerWeeklyStats, resolveRows } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { ErrorState, LoadingState } from '@components/common/AsyncState';
import { useTheme } from '../../hooks/useTheme';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const ManagerTrendChart = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [stats, setStats] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  // defensive: ensure stats is an array and log changes
  const safeStats = Array.isArray(stats) ? stats : [];
  React.useEffect(() => {
    console.log('ManagerTrendChart stats received:', stats);
  }, [stats]);

  React.useEffect(() => {
    const load = async () => {
      try {
        const user = await fetchCurrentUser();
        const leagueId = user?.league_id;
        const managerId = user?.id || user?.user_id;
        if (!leagueId || !managerId) {
          setError('Unable to determine league or user');
          setLoading(false);
          return;
        }
        const payload = await fetchManagerWeeklyStats(leagueId, managerId);
        setStats(resolveRows(payload));
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'Failed to load stats'));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // default fallback data if no stats yet or loading
  if (loading) {
    return <LoadingState message="Loading trend chart..." />;
  }
  if (error) {
    return <ErrorState message={error} />;
  }

  const weeks = safeStats.map((s) => `Week ${s.week}`);
  const actuals = safeStats.map((s) => s.actual);
  const maxima = safeStats.map((s) => s.max);

  const data = {
    labels: weeks,
    datasets: [
      {
        label: 'Actual pts',
        data: actuals,
        borderColor: 'rgba(54, 162, 235, 1)',
        backgroundColor: 'rgba(54, 162, 235, 0.1)',
        tension: 0.3,
        borderWidth: 3,
        pointRadius: 6,
        pointHoverRadius: 8,
        pointBackgroundColor: 'rgba(54, 162, 235, 1)',
        pointBorderColor: isDark ? '#ffffff' : '#0f172a',
        pointBorderWidth: 2,
      },
      {
        label: 'Optimal pts',
        data: maxima,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.1)',
        tension: 0.3,
        borderWidth: 3,
        pointRadius: 6,
        pointHoverRadius: 8,
        pointBackgroundColor: 'rgba(75, 192, 192, 1)',
        pointBorderColor: isDark ? '#ffffff' : '#0f172a',
        pointBorderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: isDark ? '#f8fafc' : '#0f172a',
          font: {
            size: 14,
          },
          padding: 15,
          usePointStyle: true,
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
          label: function (context) {
            return `${context.dataset.label}: ${context.parsed.y} points`;
          },
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Week',
          color: isDark ? '#f8fafc' : '#0f172a',
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
        },
        grid: {
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.7)',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Points Scored',
          color: isDark ? '#f8fafc' : '#0f172a',
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
        },
        grid: {
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.7)',
        },
        beginAtZero: false,
        min: 70,
        max: 150,
      },
    },
  };

  return (
    <div
      className="md:block bg-white dark:bg-slate-900 rounded-lg p-5"
      style={{ height: '500px' }}
    >
      <h3 className="text-slate-900 dark:text-slate-100 text-center mt-0 mb-4 text-base font-semibold">
        📈 Manager Performance Trends
      </h3>
      <p className="text-slate-600 dark:text-slate-400 text-sm text-center mb-4">
        Weekly scoring trends across the season
      </p>
      <Line data={data} options={options} />
    </div>
  );
};

export default ManagerTrendChart;
