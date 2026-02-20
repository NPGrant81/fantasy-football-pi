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
import WeeklyMatchupChart from '../../components/charts/WeeklyMatchupChart';
import PlayerHeatmap from '../../components/charts/PlayerHeatmap';
import './AnalyticsDashboard.css';

const AnalyticsDashboard = () => {
  return (
    <div className="analytics-dashboard">
      <div className="dashboard-header">
        <h1>📊 League Analytics</h1>
        <p>Advanced insights and visualizations for your fantasy league</p>
      </div>
      
      <div className="charts-grid">
        <div className="chart-card">
          <DraftValueBoard />
        </div>
        
        <div className="chart-card">
          <ManagerTrendChart />
        </div>

        <div className="chart-card">
          <WeeklyMatchupChart />
        </div>
        
        <div className="chart-card">
          <PlayerHeatmap />
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;