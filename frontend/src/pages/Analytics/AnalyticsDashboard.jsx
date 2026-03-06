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
import {
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

/* ignore-breakpoints */

const AnalyticsDashboard = () => {
  const [selected, setSelected] = React.useState(null); // null, 'draft','manager','weekly','heatmap'

  const charts = [
    { key: 'draft', label: 'Draft Value Analysis' },
    { key: 'efficiency', label: 'Efficiency Leaderboard' },
    { key: 'manager', label: 'Manager Performance Trends' },
    { key: 'weekly', label: 'Weekly Matchup Comparison' },
    { key: 'heatmap', label: 'Player Heatmap' },
    { key: 'trade', label: 'Trade Analyzer' },
    { key: 'rivalry', label: 'League Rivalry Graph' },
  ];

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
          <p className="text-slate-500 dark:text-slate-400">
            Select a chart above to display it.
          </p>
        );
    }
  };

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>League Analytics</h1>
        <p className={pageSubtitle}>
          Advanced insights and visualizations for your fantasy league.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {charts.map((chart) => (
          <button
            key={chart.key}
            type="button"
            className={selected === chart.key ? buttonPrimary : buttonSecondary}
            onClick={() => setSelected(chart.key)}
          >
            {chart.label}
          </button>
        ))}
      </div>

      <div className={cardSurface}>{renderChart()}</div>
    </div>
  );
};

export default AnalyticsDashboard;
