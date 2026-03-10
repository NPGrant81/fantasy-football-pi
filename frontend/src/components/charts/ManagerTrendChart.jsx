// Manager trend analysis line chart backed by analytics API weekly stats.

import React from 'react';
import { fetchCurrentUser } from '@api/commonApi';
import { fetchManagerWeeklyStats, resolveRows } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import { ErrorState, LoadingState } from '@components/common/AsyncState';
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
        pointBorderColor: '#ffffff',
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
        pointBorderColor: '#ffffff',
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
          color: '#ffffff',
          font: {
            size: 14,
          },
          padding: 15,
          usePointStyle: true,
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
        beginAtZero: false,
        min: 70,
        max: 150,
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
        📈 Manager Performance Trends
      </h3>
      <p
        style={{
          color: '#cccccc',
          fontSize: '14px',
          textAlign: 'center',
          marginBottom: '20px',
        }}
      >
        Weekly scoring trends across the season
      </p>
      <Line data={data} options={options} />
    </div>
  );
};

export default ManagerTrendChart;
