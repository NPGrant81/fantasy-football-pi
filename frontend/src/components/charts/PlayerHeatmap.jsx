import React from 'react';
import apiClient from '@api/client';
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
  const [rows, setRows] = React.useState([]);
  const [weeks, setWeeks] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    const load = async () => {
      try {
        const userRes = await apiClient.get('/auth/me');
        const leagueId = userRes.data?.league_id;
        if (!leagueId) {
          setError('League not found.');
          return;
        }

        const season = new Date().getFullYear();
        const res = await apiClient.get(
          `/analytics/league/${leagueId}/player-heatmap`,
          {
            params: { season, limit: 8, weeks: 8 },
          }
        );

        const payload = res.data || {};
        setRows(Array.isArray(payload.rows) ? payload.rows : []);
        setWeeks(Array.isArray(payload.week_labels) ? payload.week_labels : []);
      } catch (err) {
        console.error(err);
        setError(err?.message || 'Failed to load player heatmap data.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return <p>Loading player heatmap...</p>;
  }

  if (error) {
    return <p className="text-red-500">Error: {error}</p>;
  }

  if (!rows.length || !weeks.length) {
    return <p>No player heatmap data available.</p>;
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
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#4a90e2',
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
          color: '#cccccc',
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
          color: '#cccccc',
        },
        grid: {
          display: false,
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
          marginBottom: '10px',
          textAlign: 'center',
        }}
      >
        Player Performance Heatmap
      </h3>
      <p
        style={{
          color: '#cccccc',
          fontSize: '14px',
          textAlign: 'center',
          marginBottom: '20px',
        }}
      >
        Weekly fantasy scoring by player under the active league scoring profile.
      </p>
      <Chart type="matrix" data={data} options={options} />
    </div>
  );
};

export default PlayerHeatmap;
