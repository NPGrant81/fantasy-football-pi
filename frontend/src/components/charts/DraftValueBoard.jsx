// Create a React component for a Draft Value Board scatter plot
// Uses Chart.js (react-chartjs-2) to visualize fantasy football draft value
// X-axis: Average Draft Position (ADP) - lower is better
// Y-axis: Projected Points for the season
// Players above the trend line are "value picks"
// Include sample data for 15 NFL players (mix of QB, RB, WR, TE)
// Dark theme styling to match our fantasy football app
// Make the chart responsive and interactive with tooltips

import React from 'react';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Scatter } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

const DraftValueBoard = () => {
  // Sample fantasy football player data
  const players = [
    {
      name: 'Christian McCaffrey',
      position: 'RB',
      adp: 1.2,
      projectedPoints: 320,
      color: 'rgba(255, 99, 132, 0.8)',
    },
    {
      name: 'CeeDee Lamb',
      position: 'WR',
      adp: 2.5,
      projectedPoints: 290,
      color: 'rgba(54, 162, 235, 0.8)',
    },
    {
      name: 'Tyreek Hill',
      position: 'WR',
      adp: 4.8,
      projectedPoints: 285,
      color: 'rgba(54, 162, 235, 0.8)',
    },
    {
      name: 'Bijan Robinson',
      position: 'RB',
      adp: 3.1,
      projectedPoints: 275,
      color: 'rgba(255, 99, 132, 0.8)',
    },
    {
      name: 'Amon-Ra St. Brown',
      position: 'WR',
      adp: 8.5,
      projectedPoints: 270,
      color: 'rgba(54, 162, 235, 0.8)',
    },
    {
      name: 'Breece Hall',
      position: 'RB',
      adp: 6.2,
      projectedPoints: 268,
      color: 'rgba(255, 99, 132, 0.8)',
    },
    {
      name: "Ja'Marr Chase",
      position: 'WR',
      adp: 5.7,
      projectedPoints: 282,
      color: 'rgba(54, 162, 235, 0.8)',
    },
    {
      name: 'Josh Allen',
      position: 'QB',
      adp: 12.3,
      projectedPoints: 310,
      color: 'rgba(75, 192, 192, 0.8)',
    },
    {
      name: 'Travis Kelce',
      position: 'TE',
      adp: 15.8,
      projectedPoints: 195,
      color: 'rgba(255, 206, 86, 0.8)',
    },
    {
      name: 'Garrett Wilson',
      position: 'WR',
      adp: 18.4,
      projectedPoints: 245,
      color: 'rgba(54, 162, 235, 0.8)',
    },
    {
      name: 'Derrick Henry',
      position: 'RB',
      adp: 22.1,
      projectedPoints: 220,
      color: 'rgba(255, 99, 132, 0.8)',
    },
    {
      name: 'Jalen Hurts',
      position: 'QB',
      adp: 9.8,
      projectedPoints: 305,
      color: 'rgba(75, 192, 192, 0.8)',
    },
    {
      name: 'Mark Andrews',
      position: 'TE',
      adp: 28.5,
      projectedPoints: 175,
      color: 'rgba(255, 206, 86, 0.8)',
    },
    {
      name: 'Joe Mixon',
      position: 'RB',
      adp: 25.7,
      projectedPoints: 210,
      color: 'rgba(255, 99, 132, 0.8)',
    },
    {
      name: 'Cooper Kupp',
      position: 'WR',
      adp: 11.2,
      projectedPoints: 265,
      color: 'rgba(54, 162, 235, 0.8)',
    },
  ];

  // Group players by position for the chart
  const datasets = [
    {
      label: 'Running Backs',
      data: players
        .filter((p) => p.position === 'RB')
        .map((p) => ({ x: p.adp, y: p.projectedPoints, playerName: p.name })),
      backgroundColor: 'rgba(255, 99, 132, 0.6)',
      borderColor: 'rgba(255, 99, 132, 1)',
      pointRadius: 8,
      pointHoverRadius: 12,
    },
    {
      label: 'Wide Receivers',
      data: players
        .filter((p) => p.position === 'WR')
        .map((p) => ({ x: p.adp, y: p.projectedPoints, playerName: p.name })),
      backgroundColor: 'rgba(54, 162, 235, 0.6)',
      borderColor: 'rgba(54, 162, 235, 1)',
      pointRadius: 8,
      pointHoverRadius: 12,
    },
    {
      label: 'Quarterbacks',
      data: players
        .filter((p) => p.position === 'QB')
        .map((p) => ({ x: p.adp, y: p.projectedPoints, playerName: p.name })),
      backgroundColor: 'rgba(75, 192, 192, 0.6)',
      borderColor: 'rgba(75, 192, 192, 1)',
      pointRadius: 8,
      pointHoverRadius: 12,
    },
    {
      label: 'Tight Ends',
      data: players
        .filter((p) => p.position === 'TE')
        .map((p) => ({ x: p.adp, y: p.projectedPoints, playerName: p.name })),
      backgroundColor: 'rgba(255, 206, 86, 0.6)',
      borderColor: 'rgba(255, 206, 86, 1)',
      pointRadius: 8,
      pointHoverRadius: 12,
    },
  ];

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
          padding: 20,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: '#4a90e2',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          label: function (context) {
            const player = context.raw;
            return [
              `${player.playerName}`,
              `ADP: ${player.x.toFixed(1)}`,
              `Projected: ${player.y} pts`,
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
          text: 'Average Draft Position (ADP)',
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
        reverse: true, // Lower ADP numbers (better picks) on the left
      },
      y: {
        type: 'linear',
        title: {
          display: true,
          text: 'Projected Season Points',
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
      <h3
        style={{
          color: '#ffffff',
          marginTop: 0,
          marginBottom: '20px',
          textAlign: 'center',
        }}
      >
        📊 Draft Value Analysis
      </h3>
      <p
        style={{
          color: '#cccccc',
          fontSize: '14px',
          textAlign: 'center',
          marginBottom: '20px',
        }}
      >
        Players in the upper-right quadrant offer the best value (high points,
        drafted late)
      </p>
      <Scatter data={{ datasets }} options={options} />
    </div>
  );
};

export default DraftValueBoard;
