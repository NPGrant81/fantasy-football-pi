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
import { useLocation } from 'react-router-dom';
import {
  FiBarChart2,
  FiTrendingUp,
  FiUsers,
  FiActivity,
  FiGrid,
  FiShuffle,
  FiGitBranch,
  FiCompass,
  FiTrendingDown,
} from 'react-icons/fi';
import DraftValueBoard from '../../components/charts/DraftValueBoard';
import ManagerTrendChart from '../../components/charts/ManagerTrendChart';
import ManagerEfficiencyLeaderboard from '../../components/charts/ManagerEfficiencyLeaderboard';
import WeeklyMatchupChart from '../../components/charts/WeeklyMatchupChart';
import PositionalHeatmap from '../../components/charts/PositionalHeatmap';
import TradeAnalyzer from '../../components/charts/TradeAnalyzer';
import RivalryGraph from '../../components/charts/RivalryGraph';
import LuckIndexChart from '../../components/charts/LuckIndexChart';
import PlayerConsistencyChart from '../../components/charts/PlayerConsistencyChart';
import WaiverOpportunityChart from '../../components/charts/WaiverOpportunityChart';
import { LoadingState } from '@components/common/AsyncState';
import ActionTile from '@components/common/ActionTile';
import PageTemplate from '@components/layout/PageTemplate';
import {
  cardSurface,
} from '@utils/uiStandards';

/* ignore-breakpoints */

const AnalyticsDashboard = () => {
  const location = useLocation();
  const selectedFromState = location?.state?.selectedChart || null;
  const preloadedTradeContext = location?.state?.tradeAnalyzerContext || null;

  const [selected, setSelected] = React.useState(null); // null, 'draft','manager','luck','consistency','waiver','weekly','heatmap','trade','rivalry'
  const [loadingChart, setLoadingChart] = React.useState(false);

  React.useEffect(() => {
    if (selectedFromState) {
      setSelected(selectedFromState);
    }
  }, [selectedFromState]);

  const charts = [
    {
      key: 'draft',
      label: 'Draft Value Analysis',
      description: 'Compare projected output versus draft cost.',
      icon: FiBarChart2,
    },
    {
      key: 'efficiency',
      label: 'Efficiency Leaderboard',
      description: 'Rank managers by lineup efficiency trends.',
      icon: FiUsers,
    },
    {
      key: 'manager',
      label: 'Manager Performance Trends',
      description: 'View weekly actual versus optimal scoring.',
      icon: FiTrendingUp,
    },
    {
      key: 'luck',
      label: 'The Luck Index',
      description: 'Schedule analysis: actual wins vs hypothetical record.',
      icon: FiCompass,
    },
    {
      key: 'consistency',
      label: 'Player Consistency Ratings',
      description: 'Analyze player volatility and reliability for lineup planning.',
      icon: FiTrendingDown,
    },
    {
      key: 'waiver',
      label: 'Waiver Wire Opportunities',
      description: 'Breakout candidates via rolling opportunity analysis heatmap.',
      icon: FiActivity,
    },
    {
      key: 'heatmap',
      label: 'Positional Matchup Heatmap',
      description: 'Team-vs-position weakness grid with streaming signals.',
      icon: FiGrid,
    },
    {
      key: 'trade',
      label: 'Trade Analyzer',
      description: 'Model value exchange and draft-cash balancing.',
      icon: FiShuffle,
    },
    {
      key: 'rivalry',
      label: 'League Rivalry Graph',
      description: 'Visualize manager relationship intensity.',
      icon: FiGitBranch,
    },
  ];

  const handleSelectChart = (chartKey) => {
    setLoadingChart(true);
    setSelected(chartKey);
    window.setTimeout(() => setLoadingChart(false), 200);
  };

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
      case 'consistency':
        return (
          <div className="chart-card">
            <PlayerConsistencyChart />
          </div>
        );
      case 'waiver':
        return (
          <div className="chart-card">
            <WaiverOpportunityChart />
          </div>
        );
      case 'heatmap':
        return (
          <div className="chart-card">
            <PositionalHeatmap />
          </div>
        );
      case 'trade':
        return (
          <div className="chart-card">
            <TradeAnalyzer preloadedContext={preloadedTradeContext} />
          </div>
        );
      case 'luck':
        return (
          <div className="chart-card">
            <LuckIndexChart />
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
    <PageTemplate
      title="League Analytics"
      subtitle="Advanced insights and visualizations for your fantasy league."
    >

      <div className="mx-auto grid w-full max-w-6xl grid-cols-2 gap-2 md:grid-cols-2 md:gap-3 xl:grid-cols-3">
        {charts.map((chart) => (
          <ActionTile
            key={chart.key}
            icon={chart.icon}
            title={chart.label}
            description={chart.description}
            selected={selected === chart.key}
            onClick={() => handleSelectChart(chart.key)}
            disabled={loadingChart}
          />
        ))}
      </div>

      <div className={cardSurface}>
        {loadingChart ? (
          <LoadingState message="Loading analytics view..." className="text-sm text-slate-500" />
        ) : (
          renderChart()
        )}
      </div>
    </PageTemplate>
  );
};

export default AnalyticsDashboard;
