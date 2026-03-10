import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import {
  fetchWeeklyMatchupsAnalytics,
  resolveRows,
} from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { EmptyState, ErrorState, LoadingState } from '@components/common/AsyncState';
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
  const [selectedWeek, setSelectedWeek] = React.useState(null);
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
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#4a90e2',
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
          color: '#cccccc',
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
        beginAtZero: true,
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
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
        }}
      >
        <h3 style={{ color: '#ffffff', margin: 0 }}>Weekly Matchup Comparison</h3>
        <select
          value={selectedRow.week}
          onChange={(e) => setSelectedWeek(Number(e.target.value))}
          style={{
            padding: '8px 16px',
            backgroundColor: '#1a1a1a',
            color: '#ffffff',
            border: '1px solid #4a90e2',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
          }}
        >
          {rows.map((row) => (
            <option key={row.week} value={row.week}>
              Week {row.week}
            </option>
          ))}
        </select>
      </div>
      <p style={{ color: '#cccccc', fontSize: '14px', marginBottom: '20px' }}>
        Team scoring comparison for the selected week.
      </p>
      <Bar data={data} options={options} />
    </div>
  );
};

export default WeeklyMatchupChart;
