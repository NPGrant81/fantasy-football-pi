import React, { useState, useEffect } from 'react';
import { fetchCurrentUser, fetchLeagueOwners } from '@api/commonApi';
import { fetchRosterStrengthAnalytics } from '@api/analyticsApi';
import { normalizeApiError } from '@api/fetching';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

export default function TradeAnalyzer() {
  const [owners, setOwners] = useState([]);
  const [leagueId, setLeagueId] = useState(null);
  const [a, setA] = useState(null);
  const [b, setB] = useState(null);
  const [dataA, setDataA] = useState(null);
  const [dataB, setDataB] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadOwners() {
      try {
        const user = await fetchCurrentUser();
        const lid = user?.league_id;
        setLeagueId(lid);
        if (!lid) return;
        const ownersPayload = await fetchLeagueOwners(lid);
        setOwners(ownersPayload || []);
      } catch (err) {
        console.error(err);
        setError(normalizeApiError(err, 'failed to load owners'));
      }
    }
    loadOwners();
  }, []);

  const fetchStrength = React.useCallback(
    async (ownerId, setter) => {
      if (!leagueId || !ownerId) return;
      try {
        const payload = await fetchRosterStrengthAnalytics(leagueId, ownerId);
        const rows = payload && payload.rows ? payload.rows : payload;
        const counts = rows?.[ownerId] || {};
        setter(counts);
      } catch (err) {
        console.error(err);
      }
    },
    [leagueId]
  );

  useEffect(() => {
    fetchStrength(a, setDataA);
  }, [a, fetchStrength]);
  useEffect(() => {
    fetchStrength(b, setDataB);
  }, [b, fetchStrength]);

  const labels = ['QB', 'RB', 'WR', 'TE'];
  const makeDataset = (counts, label, color) => {
    if (!counts) return null;
    return {
      label,
      data: labels.map((l) => counts[l] || 0),
      backgroundColor: color + '33',
      borderColor: color,
      borderWidth: 2,
      fill: true,
    };
  };

  const data = {
    labels,
    datasets: [
      makeDataset(
        dataA,
        owners.find((o) => o.id === a)?.username || 'A',
        'rgba(54,162,235)'
      ),
      makeDataset(
        dataB,
        owners.find((o) => o.id === b)?.username || 'B',
        'rgba(255,99,132)'
      ),
    ].filter(Boolean),
  };

  const options = {
    scales: {
      r: {
        suggestedMin: 0,
        suggestedMax: 10,
        ticks: { color: '#fff' },
        grid: { color: '#555' },
        angleLines: { color: '#555' },
      },
    },
    plugins: {
      legend: { labels: { color: '#fff' } },
      tooltip: { enabled: true },
    },
  };

  return (
    <div className="p-4 md:p-6 text-white">
      <h3 className="text-xl font-bold mb-4">Trade Analyzer</h3>
      {error && <p className="text-red-400">{error}</p>}
      <div className="flex gap-4 mb-4">
        <div>
          <label htmlFor="trade-owner-a" className="block mb-1">
            Owner A
          </label>
          <select
            id="trade-owner-a"
            className="p-2 bg-slate-800 rounded"
            value={a || ''}
            onChange={(e) => setA(Number(e.target.value) || null)}
          >
            <option value="">--select--</option>
            {owners.map((o) => (
              <option key={o.id} value={o.id}>
                {o.username || o.id}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="trade-owner-b" className="block mb-1">
            Owner B
          </label>
          <select
            id="trade-owner-b"
            className="p-2 bg-slate-800 rounded"
            value={b || ''}
            onChange={(e) => setB(Number(e.target.value) || null)}
          >
            <option value="">--select--</option>
            {owners.map((o) => (
              <option key={o.id} value={o.id}>
                {o.username || o.id}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="w-full h-64">
        <Radar data={data} options={options} />
      </div>
    </div>
  );
}
