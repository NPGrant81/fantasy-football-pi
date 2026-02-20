import React from 'react';
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
  // Mock player performance data (weeks 1-6)
  const players = ['C. McCaffrey', 'T. Hill', 'J. Chase', 'B. Hall', 'T. Kelce'];
  const weeks = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'];

  // Fantasy points scored each week (mock data)
  const performanceData = [
    // McCaffrey
    { x: 0, y: 0, v: 24.5 },
    { x: 1, y: 0, v: 18.2 },
    { x: 2, y: 0, v: 32.8 },
    { x: 3, y: 0, v: 28.1 },
    { x: 4, y: 0, v: 15.4 },
    { x: 5, y: 0, v: 26.7 },
    // Tyreek Hill
    { x: 0, y: 1, v: 21.3 },
    { x: 1, y: 1, v: 14.8 },
    { x: 2, y: 1, v: 28.5 },
    { x: 3, y: 1, v: 31.2 },
    { x: 4, y: 1, v: 19.6 },
    { x: 5, y: 1, v: 24.1 },
    // Ja'Marr Chase
    { x: 0, y: 2, v: 18.7 },
    { x: 1, y: 2, v: 25.3 },
    { x: 2, y: 2, v: 12.4 },
    { x: 3, y: 2, v: 29.8 },
    { x: 4, y: 2, v: 22.1 },
    { x: 5, y: 2, v: 16.9 },
    // Breece Hall
    { x: 0, y: 3, v: 22.4 },
    { x: 1, y: 3, v: 16.7 },
    { x: 2, y: 3, v: 8.3 },
    { x: 3, y: 3, v: 24.6 },
    { x: 4, y: 3, v: 28.9 },
    { x: 5, y: 3, v: 19.2 },
    // Travis Kelce
    { x: 0, y: 4, v: 15.2 },
    { x: 1, y: 4, v: 11.8 },
    { x: 2, y: 4, v: 18.5 },
    { x: 3, y: 4, v: 14.3 },
    { x: 4, y: 4, v: 9.7 },
    { x: 5, y: 4, v: 16.4 },
  ];

  const data = {
    datasets: [
      {
        label: 'Fantasy Points',
        data: performanceData,
        backgroundColor(context) {
          const value = context.dataset.data[context.dataIndex].v;
          const alpha = (value / 35).toFixed(2); // Scale color intensity
          if (value >= 25) return `rgba(34, 197, 94, ${alpha})`; // Green for high
          if (value >= 15) return `rgba(250, 204, 21, ${alpha})`; // Yellow for medium
          return `rgba(239, 68, 68, ${alpha})`; // Red for low
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
    <div style={{ height: '500px', padding: '20px', backgroundColor: '#2a2a2a', borderRadius: '8px' }}>
      <h3 style={{ color: '#ffffff', marginTop: 0, marginBottom: '10px', textAlign: 'center' }}>
        🔥 Player Performance Heatmap
      </h3>
      <p style={{ color: '#cccccc', fontSize: '14px', textAlign: 'center', marginBottom: '20px' }}>
        Weekly fantasy points by player (Green = Hot 🔥, Red = Cold ❄️)
      </p>
      <Chart type="matrix" data={data} options={options} />
    </div>
  );
};

export default PlayerHeatmap;