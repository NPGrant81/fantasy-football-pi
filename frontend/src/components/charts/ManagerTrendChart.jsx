// Create a React component for Manager Trend Analysis line chart
// Uses Chart.js to show weekly scoring trends for all league managers
// X-axis: Week numbers (1-17 for NFL season)
// Y-axis: Points scored that week
// Multiple lines (one per manager) with different colors
// Include a legend showing team names
// Add tooltips showing exact points on hover
// Include sample data for 4 managers across 6 weeks
// Dark theme with vibrant team colors (blue, red, green, orange)
// Make it responsive and animated

import React from 'react';
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
  // Sample weekly scoring data for 4 managers
  const weeks = ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'];
  
  const managersData = [
    {
      teamName: 'The Big Show',
      owner: 'NPGrant81',
      scores: [110, 125, 98, 140, 115, 132],
      color: 'rgba(54, 162, 235, 1)',
    },
    {
      teamName: 'Thunder Dome',
      owner: 'Coach_Mike',
      scores: [85, 90, 105, 115, 108, 95],
      color: 'rgba(255, 99, 132, 1)',
    },
    {
      teamName: 'Gridiron Giants',
      owner: 'SarahJ',
      scores: [95, 88, 112, 102, 125, 118],
      color: 'rgba(75, 192, 192, 1)',
    },
    {
      teamName: 'End Zone Warriors',
      owner: 'TommyT',
      scores: [102, 115, 89, 98, 110, 103],
      color: 'rgba(255, 206, 86, 1)',
    },
  ];

  const data = {
    labels: weeks,
    datasets: managersData.map(manager => ({
      label: manager.teamName,
      data: manager.scores,
      borderColor: manager.color,
      backgroundColor: manager.color.replace('1)', '0.1)'),
      tension: 0.3,
      borderWidth: 3,
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: manager.color,
      pointBorderColor: '#ffffff',
      pointBorderWidth: 2,
    })),
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
          label: function(context) {
            return `${context.dataset.label}: ${context.parsed.y} points`;
          }
        }
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
    <div style={{ height: '500px', padding: '20px', backgroundColor: '#2a2a2a', borderRadius: '8px' }}>
      <h3 style={{ color: '#ffffff', marginTop: 0, marginBottom: '20px', textAlign: 'center' }}>
        📈 Manager Performance Trends
      </h3>
      <p style={{ color: '#cccccc', fontSize: '14px', textAlign: 'center', marginBottom: '20px' }}>
        Weekly scoring trends across the season
      </p>
      <Line data={data} options={options} />
    </div>
  );
};

export default ManagerTrendChart;