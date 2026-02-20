import React, { useState } from 'react';
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
  const [selectedWeek, setSelectedWeek] = useState(6);

  // Mock matchup data for Week 6
  const matchupData = {
    1: [
      { team: 'The Big Show', score: 145 },
      { team: 'Thunder Dome', score: 112 },
      { team: 'Gridiron Giants', score: 128 },
      { team: 'End Zone Warriors', score: 98 },
    ],
    2: [
      { team: 'The Big Show', score: 132 },
      { team: 'Thunder Dome', score: 118 },
      { team: 'Gridiron Giants', score: 105 },
      { team: 'End Zone Warriors', score: 125 },
    ],
    3: [
      { team: 'The Big Show', score: 118 },
      { team: 'Thunder Dome', score: 108 },
      { team: 'Gridiron Giants', score: 142 },
      { team: 'End Zone Warriors', score: 95 },
    ],
    4: [
      { team: 'The Big Show', score: 155 },
      { team: 'Thunder Dome', score: 125 },
      { team: 'Gridiron Giants', score: 115 },
      { team: 'End Zone Warriors', score: 110 },
    ],
    5: [
      { team: 'The Big Show', score: 128 },
      { team: 'Thunder Dome', score: 115 },
      { team: 'Gridiron Giants', score: 138 },
      { team: 'End Zone Warriors', score: 118 },
    ],
    6: [
      { team: 'The Big Show', score: 142 },
      { team: 'Thunder Dome', score: 102 },
      { team: 'Gridiron Giants', score: 125 },
      { team: 'End Zone Warriors', score: 108 },
    ],
  };

  const currentWeekData = matchupData[selectedWeek];

  // Sort by score descending
  const sortedData = [...currentWeekData].sort((a, b) => b.score - a.score);

  const data = {
    labels: sortedData.map((d) => d.team),
    datasets: [
      {
        label: `Week ${selectedWeek} Scores`,
        data: sortedData.map((d) => d.score),
        backgroundColor: [
          'rgba(54, 162, 235, 0.8)',
          'rgba(255, 99, 132, 0.8)',
          'rgba(75, 192, 192, 0.8)',
          'rgba(255, 206, 86, 0.8)',
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)',
          'rgba(255, 99, 132, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(255, 206, 86, 1)',
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
          label: function (context) {
            return `Score: ${context.parsed.y} points`;
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
        <h3 style={{ color: '#ffffff', margin: 0 }}>
          📊 Weekly Matchup Comparison
        </h3>
        <select
          value={selectedWeek}
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
          {[1, 2, 3, 4, 5, 6].map((week) => (
            <option key={week} value={week}>
              Week {week}
            </option>
          ))}
        </select>
      </div>
      <p style={{ color: '#cccccc', fontSize: '14px', marginBottom: '20px' }}>
        Team performance comparison for the selected week
      </p>
      <Bar data={data} options={options} />
    </div>
  );
};

export default WeeklyMatchupChart;
