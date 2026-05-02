import React, { useState, useEffect } from 'react';
import { Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { useActiveLeague } from '@context/LeagueContext';
import { fetchLuckIndexAnalytics } from '@api/analyticsApi';
import { LoadingState, ErrorState } from '@components/common/AsyncState';
import { useTheme } from '../../hooks/useTheme';

ChartJS.register(CategoryScale, LinearScale, PointElement, Tooltip, Legend, Filler);

export default function LuckIndexChart() {
  const leagueId = useActiveLeague();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!leagueId) return;
    
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await fetchLuckIndexAnalytics(leagueId);
        setData(payload);
      } catch (err) {
        setError(err?.message || 'Failed to load luck index data');
      } finally {
        setLoading(false);
      }
    };
    
    load();
  }, [leagueId]);

  if (loading) {
    return <LoadingState message="Calculating luck index..." className="h-96" />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="text-center p-8 text-slate-600 dark:text-slate-400">
        <p>No luck index data available.</p>
      </div>
    );
  }

  const medians = data.medians || {};
  const median_pf = medians.pf || 0;
  const median_pa = medians.pa || 0;

  // Prepare data for scatter chart
  const chartData = {
    datasets: [
      {
        label: 'Teams',
        data: data.rows.map((r) => ({
          x: r.pf,
          y: r.pa,
          label: r.team_name || r.owner_name,
          luck: r.luck,
          record: r.actual_record,
          hypothetical: r.hypothetical_wins.toFixed(1),
        })),
        backgroundColor: data.rows.map((r) => {
          // Green for lucky, red for unlucky
          if (r.luck > 0) {
            const intensity = Math.min(r.luck / 3, 1);
            return `rgba(16, 185, 129, ${0.3 + intensity * 0.4})`;
          } else if (r.luck < 0) {
            const intensity = Math.min(-r.luck / 3, 1);
            return `rgba(239, 68, 68, ${0.3 + intensity * 0.4})`;
          } else {
            return 'rgba(148, 163, 184, 0.4)';
          }
        }),
        borderColor: data.rows.map((r) => {
          if (r.luck > 0) return '#10b981';
          if (r.luck < 0) return '#ef4444';
          return '#64748b';
        }),
        borderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    aspectRatio: 1.5,
    plugins: {
      legend: {
        display: true,
        position: 'top',
      },
      tooltip: {
        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.97)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        bodyColor: isDark ? '#cbd5e1' : '#334155',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        borderWidth: 1,
        padding: 10,
        titleFont: { size: 12, weight: 'bold' },
        bodyFont: { size: 11 },
        callbacks: {
          title: (context) => context[0].raw.label,
          label: (context) => {
            const point = context.raw;
            return [
              `Record: ${point.record}`,
              `Hyp. W: ${point.hypothetical}`,
              `Luck: ${point.luck > 0 ? '+' : ''}${point.luck.toFixed(1)}`,
              `PF: ${Math.round(context.parsed.x)}, PA: ${Math.round(context.parsed.y)}`,
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
          text: 'Points For (Scoring Efficiency)',
          color: isDark ? '#f8fafc' : '#1f2937',
          font: { size: 12, weight: 'bold' },
        },
        grid: {
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.5)',
          drawBorder: true,
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
        },
      },
      y: {
        title: {
          display: true,
          text: 'Points Against (Schedule Strength)',
          color: isDark ? '#f8fafc' : '#1f2937',
          font: { size: 12, weight: 'bold' },
        },
        grid: {
          color: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.5)',
          drawBorder: true,
        },
        ticks: {
          color: isDark ? '#94a3b8' : '#475569',
        },
      },
    },
  };

  return (
    <div className="w-full bg-white dark:bg-slate-900/30 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
      {/* Chart */}
      <div className="mb-6 bg-slate-50 dark:bg-slate-900/50 rounded p-4">
        <Scatter data={chartData} options={chartOptions} />
        
        {/* Median lines explanation */}
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="text-slate-600 dark:text-slate-400">
            <span className="font-semibold">Median PF:</span> {median_pf.toFixed(0)}
            <div className="text-[10px] italic">Vertical divider</div>
          </div>
          <div className="text-slate-600 dark:text-slate-400">
            <span className="font-semibold">Median PA:</span> {median_pa.toFixed(0)}
            <div className="text-[10px] italic">Horizontal divider</div>
          </div>
        </div>
      </div>

      {/* Legend and explanation */}
      <div className="space-y-4">
        <div className="text-sm text-slate-700 dark:text-slate-300">
          <p className="font-semibold mb-2">How to Read This Chart:</p>
          <ul className="space-y-1 text-xs">
            <li>
              <span className="font-medium">X-Axis (Points For):</span> Your team's scoring output
            </li>
            <li>
              <span className="font-medium">Y-Axis (Points Against):</span> Opponent strength (dashed lines = league medians)
            </li>
            <li>
              <span className="font-medium">Color (Green→Red):</span> Luck Index (green = lucky, red = unlucky)
            </li>
            <li>
              <span className="font-medium">Four Quadrants:</span> Good/Bad scoring vs Lucky/Unlucky scheduling
            </li>
          </ul>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-slate-50 dark:bg-slate-900/50 p-3 rounded">
          <div className="border-l-4 border-emerald-500 pl-2">
            <p className="font-semibold text-emerald-700 dark:text-emerald-300">Good/Lucky</p>
            <p className="text-slate-600 dark:text-slate-400">High PF, easy schedule</p>
          </div>
          <div className="border-l-4 border-red-500 pl-2">
            <p className="font-semibold text-red-700 dark:text-red-300">Good/Unlucky</p>
            <p className="text-slate-600 dark:text-slate-400">High PF, tough schedule</p>
          </div>
          <div className="border-l-4 border-amber-500 pl-2">
            <p className="font-semibold text-amber-700 dark:text-amber-300">Bad/Lucky</p>
            <p className="text-slate-600 dark:text-slate-400">Low PF, easy schedule</p>
          </div>
          <div className="border-l-4 border-slate-500 pl-2">
            <p className="font-semibold text-slate-700 dark:text-slate-300">Bad/Unlucky</p>
            <p className="text-slate-600 dark:text-slate-400">Low PF, tough schedule</p>
          </div>
        </div>

        {/* Team stats table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-100 dark:bg-slate-800">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-900 dark:text-slate-100">Team</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-900 dark:text-slate-100">Record</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-900 dark:text-slate-100">PF</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-900 dark:text-slate-100">PA</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-900 dark:text-slate-100">Hyp. W</th>
                <th className="px-3 py-2 text-center font-semibold text-slate-900 dark:text-slate-100">Luck</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-900 dark:text-slate-100">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {data.rows.map((row, idx) => (
                <tr
                  key={idx}
                  className="bg-white dark:bg-slate-900/20 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                >
                  <td className="px-3 py-2 text-slate-900 dark:text-slate-100">{row.team_name}</td>
                  <td className="px-3 py-2 text-center text-slate-700 dark:text-slate-300">
                    {row.actual_record}
                  </td>
                  <td className="px-3 py-2 text-center text-slate-700 dark:text-slate-300">
                    {row.pf.toFixed(0)}
                  </td>
                  <td className="px-3 py-2 text-center text-slate-700 dark:text-slate-300">
                    {row.pa.toFixed(0)}
                  </td>
                  <td className="px-3 py-2 text-center text-slate-700 dark:text-slate-300">
                    {row.hypothetical_wins.toFixed(1)}
                  </td>
                  <td className={`px-3 py-2 text-center font-semibold ${
                    row.luck > 0
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : row.luck < 0
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-slate-600 dark:text-slate-400'
                  }`}>
                    {row.luck > 0 ? '+' : ''}{row.luck.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                    {row.quadrant}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
