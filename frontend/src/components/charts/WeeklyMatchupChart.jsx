import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import {
  fetchWeeklyMatchupsAnalytics,
  resolveRows,
} from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
import { useTheme } from '../../hooks/useTheme';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const WeeklyMatchupChart = () => {
  const { theme } = useTheme();
  const [selectedWeek, setSelectedWeek] = React.useState(null);
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
        const payload = await fetchWeeklyMatchupsAnalytics(leagueId, season);
        const safeRows = resolveRows(payload);
        setRows(safeRows);
        if (safeRows.length) {
          setSelectedWeek(Number(safeRows[safeRows.length - 1].week));
        }
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'Failed to load weekly matchup data.'));
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return <LoadingState message="Loading weekly matchup comparison..." />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!rows.length) {
    return <EmptyState message="No weekly matchup data available." />;
  }

  const selectedRow = rows.find((row) => Number(row.week) === Number(selectedWeek)) || rows[0];
  const sortedData = [...(selectedRow.entries || [])].sort(
    (a, b) => Number(b.score || 0) - Number(a.score || 0)
  );

  const data = {
    labels: sortedData.map((d) => d.team),
    datasets: [
      {
        label: `Week ${selectedRow.week} Scores`,
        data: sortedData.map((d) => Number(d.score || 0)),
        backgroundColor: [
          'rgba(54, 162, 235, 0.8)',
          'rgba(255, 99, 132, 0.8)',
          'rgba(75, 192, 192, 0.8)',
          'rgba(255, 206, 86, 0.8)',
          'rgba(153, 102, 255, 0.8)',
          'rgba(255, 159, 64, 0.8)',
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)',
          'rgba(255, 99, 132, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(255, 159, 64, 1)',
        ],
        borderWidth: 2,
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
          label(context) {
            return `Score: ${context.parsed.y.toFixed(2)} points`;
          },
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: chartText,
          font: {
            size: 12,
          },
        },
        grid: {
          display: false,
        },
      },
      y: {
        title: {
          display: true,
          text: 'Points Scored',
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
        beginAtZero: true,
      },
    },
  };

  return (
    <div className="md:block h-[500px] rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900/40">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="m-0 text-lg font-semibold text-slate-900 dark:text-slate-100">Weekly Matchup Comparison</h3>
        <select
          value={selectedRow.week}
          onChange={(e) => setSelectedWeek(Number(e.target.value))}
          className="cursor-pointer rounded border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
        >
          {rows.map((row) => (
            <option key={row.week} value={row.week}>
              Week {row.week}
            </option>
          ))}
        </select>
      </div>
      <p className="mb-5 text-sm text-slate-600 dark:text-slate-400">
        Team scoring comparison for the selected week.
      </p>
      <Bar data={data} options={options} />
    </div>
  );
};

export default WeeklyMatchupChart;
