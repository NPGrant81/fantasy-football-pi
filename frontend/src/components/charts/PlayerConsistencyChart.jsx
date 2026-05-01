import React, { useState, useEffect } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { useActiveLeague } from '@context/LeagueContext';
import { fetchPlayerConsistencyAnalytics } from '@api/analyticsApi';
import { LoadingState, ErrorState } from '@components/common/AsyncState';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const ConsistencyBox = ({ player, type = 'reliable' }) => {
  const { player_name, position, avg, floor, ceiling, median, stdev, variance, reliability_score } = player;
  const range = ceiling - floor;
  const rangePercent = range > 0 ? Math.round(((median - floor) / range) * 100) : 50;

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded p-3 mb-3 bg-white dark:bg-slate-900/30">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">{player_name}</p>
          <span className="inline-block px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs rounded">
            {position}
          </span>
        </div>
        <div className="text-right">
          <p className="font-bold text-lg text-slate-900 dark:text-slate-100">{avg.toFixed(1)}</p>
          <p className="text-xs text-slate-600 dark:text-slate-400">avg</p>
        </div>
      </div>

      {/* Mini box-and-whisker visualization */}
      <div className="space-y-2">
        <div>
          <p className="text-xs text-slate-600 dark:text-slate-400 mb-1">Floor → Median → Ceiling</p>
          <div className="flex items-center gap-1 h-6 bg-slate-100 dark:bg-slate-800 rounded relative px-1">
            {/* Floor marker */}
            <div
              className="absolute h-4 w-0.5 bg-red-500"
              style={{ left: `${(floor / ceiling) * 100}%` }}
              title={`Floor: ${floor.toFixed(1)}`}
            />
            {/* Median marker */}
            <div
              className="absolute h-4 w-1 bg-indigo-600 dark:bg-indigo-400"
              style={{ left: `${(median / ceiling) * 100}%` }}
              title={`Median: ${median.toFixed(1)}`}
            />
            {/* Ceiling marker */}
            <div
              className="absolute h-4 w-0.5 bg-green-500"
              style={{ left: `${(ceiling / ceiling) * 100}%` }}
              title={`Ceiling: ${ceiling.toFixed(1)}`}
            />
            <div className="flex-1 text-xs text-slate-600 dark:text-slate-400 ml-2">
              {floor.toFixed(1)} – {median.toFixed(1)} – {ceiling.toFixed(1)}
            </div>
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-slate-600 dark:text-slate-400">Std Dev:</span>
            <p className="font-semibold text-slate-900 dark:text-slate-100">{stdev.toFixed(2)}</p>
          </div>
          <div>
            <span className="text-slate-600 dark:text-slate-400">Variance:</span>
            <p className="font-semibold text-slate-900 dark:text-slate-100">{variance.toFixed(2)}</p>
          </div>
          <div className="col-span-2">
            <span className="text-slate-600 dark:text-slate-400">Reliability:</span>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded overflow-hidden">
                <div
                  className={`h-full ${
                    reliability_score > 0.8
                      ? 'bg-emerald-500'
                      : reliability_score > 0.7
                      ? 'bg-cyan-500'
                      : 'bg-amber-500'
                  }`}
                  style={{ width: `${reliability_score * 100}%` }}
                />
              </div>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{(reliability_score * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default function PlayerConsistencyChart() {
  const leagueId = useActiveLeague();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!leagueId) return;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchPlayerConsistencyAnalytics(leagueId);
        setData(response.data);
      } catch (err) {
        setError(err?.message || 'Failed to load player consistency data');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [leagueId]);

  if (loading) {
    return <LoadingState message="Analyzing player consistency..." className="h-96" />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!data || (!data.most_reliable?.length && !data.most_volatile?.length)) {
    return (
      <div className="text-center p-8 text-slate-600 dark:text-slate-400">
        <p>No player consistency data available.</p>
      </div>
    );
  }

  // Prepare data for average comparison chart
  const allPlayers = [...(data.most_reliable || []), ...(data.most_volatile || [])];
  const chartData = {
    labels: allPlayers.map((p) => `${p.player_name.split(' ')[1] || p.player_name}`),
    datasets: [
      {
        label: 'Average Fantasy Points',
        data: allPlayers.map((p) => p.avg),
        backgroundColor: allPlayers.map((p) =>
          data.most_reliable?.find((mr) => mr.player_id === p.player_id)
            ? 'rgba(16, 185, 129, 0.6)'
            : 'rgba(239, 68, 68, 0.6)'
        ),
        borderColor: allPlayers.map((p) =>
          data.most_reliable?.find((mr) => mr.player_id === p.player_id)
            ? '#10b981'
            : '#ef4444'
        ),
        borderWidth: 2,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    aspectRatio: 2,
    plugins: {
      legend: { display: true },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        padding: 10,
        callbacks: {
          afterLabel: (context) => {
            const player = allPlayers[context.dataIndex];
            return [
              `Floor: ${player.floor.toFixed(1)}`,
              `Median: ${player.median.toFixed(1)}`,
              `Ceiling: ${player.ceiling.toFixed(1)}`,
              `StdDev: ${player.stdev.toFixed(2)}`,
            ];
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: { display: true, text: 'Fantasy Points' },
      },
    },
  };

  return (
    <div className="w-full bg-white dark:bg-slate-900/30 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
      {/* Overview Chart */}
      <div className="mb-6 bg-slate-50 dark:bg-slate-900/50 rounded p-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">
          Player Scoring Overview
        </h3>
        <Bar data={chartData} options={chartOptions} />
        <div className="mt-2 flex gap-4 text-xs justify-center">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-emerald-500" />
            <span className="text-slate-600 dark:text-slate-400">Most Reliable</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-500" />
            <span className="text-slate-600 dark:text-slate-400">Most Volatile</span>
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Most Reliable */}
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3 flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            Most Reliable (Low Variance)
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
            Best for consistent lineup depth and predictable scoring
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {data.most_reliable?.map((player) => (
              <ConsistencyBox key={player.player_id} player={player} type="reliable" />
            ))}
          </div>
        </div>

        {/* Most Volatile */}
        <div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3 flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500" />
            Most Volatile (High Variance)
          </h3>
          <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
            High ceiling potential but unreliable for key matchups; monitor for breakout weeks
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {data.most_volatile?.map((player) => (
              <ConsistencyBox key={player.player_id} player={player} type="volatile" />
            ))}
          </div>
        </div>
      </div>

      {/* Explanation */}
      <div className="mt-6 p-4 bg-slate-50 dark:bg-slate-900/50 rounded text-xs text-slate-700 dark:text-slate-300 space-y-2">
        <p className="font-semibold">How to Use This Data:</p>
        <ul className="list-disc list-inside space-y-1">
          <li>
            <span className="font-medium">Lineup Planning:</span> Reliable players = safe floor; volatile players = upside potential
          </li>
          <li>
            <span className="font-medium">Waiver Wire:</span> High-ceiling volatility players are pickup candidates for upside weeks
          </li>
          <li>
            <span className="font-medium">Bench Planning:</span> Pair reliable starters with volatile bench depth
          </li>
          <li>
            <span className="font-medium">Trade Analysis:</span> Use reliability vs average to assess trade risk/reward
          </li>
        </ul>
        <p className="pt-2 italic">
          Reliability Score: (avg ÷ (avg + std.dev)) — measures how consistently a player hits their average. 1.0 = perfect consistency.
        </p>
      </div>
    </div>
  );
}
