// Create a React dashboard page for fantasy football analytics
// Import DraftValueBoard and ManagerTrendChart components
// Layout: Two-column grid on desktop, stacked on mobile
// Include a page header "📊 League Analytics"
// Each chart gets its own card/panel with a title
// Card 1: "Draft Value Analysis" with DraftValueBoard
// Card 2: "Manager Performance Trends" with ManagerTrendChart
// Use CSS Grid or Flexbox for responsive layout
// Dark theme background (#1a1a1a), cards with subtle borders
// Add padding and spacing for clean look

import React from 'react';
import DraftValueBoard from '../../components/charts/DraftValueBoard';
import ManagerTrendChart from '../../components/charts/ManagerTrendChart';
import ManagerEfficiencyLeaderboard from '../../components/charts/ManagerEfficiencyLeaderboard';
import WeeklyMatchupChart from '../../components/charts/WeeklyMatchupChart';
import PlayerHeatmap from '../../components/charts/PlayerHeatmap';
import TradeAnalyzer from '../../components/charts/TradeAnalyzer';
import RivalryGraph from '../../components/charts/RivalryGraph';
import './AnalyticsDashboard.css';

const AnalyticsDashboard = () => {
  const [selected, setSelected] = React.useState(null); // null, 'draft','manager','weekly','heatmap'

  const renderChart = () => {
    switch (selected) {
      case 'draft':
        return (
          <div className="chart-card">
            <DraftValueBoard />
          </div>
        );
      case 'efficiency':
        return (
          <div className="chart-card">
            <ManagerEfficiencyLeaderboard />
          </div>
        );
      case 'manager':
        return (
          <div className="chart-card">
            <ManagerTrendChart />
          </div>
        );
      case 'weekly':
        return (
          <div className="chart-card">
            <WeeklyMatchupChart />
          </div>
        );
      case 'heatmap':
        return (
          <div className="chart-card">
            <PlayerHeatmap />
          </div>
        );
      case 'trade':
        return (
          <div className="chart-card">
            <TradeAnalyzer />
          </div>
        );
      case 'rivalry':
        return (
          <div className="chart-card">
            <RivalryGraph />
          </div>
        );
      default:
        return (
          <p className="no-selection">Select a chart above to display it.</p>
        );
    }
  };

  return (
    <div className="analytics-dashboard">
      <div className="dashboard-header">
        <h1>📊 League Analytics</h1>
        <p>Advanced insights and visualizations for your fantasy league</p>
      </div>

      <div className="button-row">
        <button
          className={selected === 'draft' ? 'active' : ''}
          onClick={() => setSelected('draft')}
        >
          Draft Value Analysis
        </button>
        <button
          className={selected === 'efficiency' ? 'active' : ''}
          onClick={() => setSelected('efficiency')}
        >
          Efficiency Leaderboard
        </button>
        <button
          className={selected === 'manager' ? 'active' : ''}
          onClick={() => setSelected('manager')}
        >
          Manager Performance Trends
        </button>
        <button
          className={selected === 'weekly' ? 'active' : ''}
          onClick={() => setSelected('weekly')}
        >
          Weekly Matchup Comparison
        </button>
        <button
          className={selected === 'heatmap' ? 'active' : ''}
          onClick={() => setSelected('heatmap')}
        >
          Player Heatmap
        </button>
        <button
          className={selected === 'trade' ? 'active' : ''}
          onClick={() => setSelected('trade')}
        >
          Trade Analyzer
        </button>
        <button
          className={selected === 'rivalry' ? 'active' : ''}
          onClick={() => setSelected('rivalry')}
        >
          Rivalry Graph
        </button>
      </div>

      <div className="charts-grid">{renderChart()}</div>
    </div>
  );
};

export default AnalyticsDashboard;
