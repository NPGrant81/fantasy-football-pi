import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '@api/client';
import { useActiveLeague } from '@context/LeagueContext';
import { EmptyState, LoadingState } from '@components/common/AsyncState';
import PageTemplate from '@components/layout/PageTemplate';
import { cardSurface } from '@utils/uiStandards';
import {
  StandardTable,
  StandardTableHead,
  StandardTableRow,
} from '@components/table/TablePrimitives';
import { tableCell, tableCellNumeric } from '@utils/uiStandards';
import BracketAccordion from '../home/components/BracketAccordion';
import { FiAward, FiTrendingUp, FiBarChart2 } from 'react-icons/fi';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const CHART_PALETTE = ['#06b6d4', '#22c55e', '#f59e0b', '#a78bfa', '#f97316', '#e11d48', '#84cc16'];
const CHAMPION_TOP_PLACE_RANKS = [1, 2, 3, 4];

const AWARD_DISPLAY_RULES = [
  {
    key: 'toilet-bowl-winner',
    label: 'Toilet Bowl Winner',
    patterns: [/toilet\s*bowl.*winner/i, /consolation.*winner/i],
  },
  {
    key: 'toilet-bowl-loser',
    label: 'Toilet Bowl Loser',
    patterns: [/toilet\s*bowl.*loser/i, /consolation.*loser/i],
  },
  {
    key: 'best-single-game-points',
    label: 'Best Single Game Points Total',
    patterns: [/best.*single.*game.*point/i, /most.*single.*game.*point/i, /high.*single.*game.*point/i],
  },
  {
    key: 'best-season-points',
    label: 'Best Season Total Points',
    patterns: [/best.*season.*point/i, /most.*season.*point/i, /high.*season.*point/i],
  },
  {
    key: 'worst-single-game-points',
    label: 'Worst Single Game Points Total',
    patterns: [/worst.*single.*game.*point/i, /least.*single.*game.*point/i, /low.*single.*game.*point/i],
  },
  {
    key: 'worst-season-points',
    label: 'Worst Single Season Points Total',
    patterns: [/worst.*season.*point/i, /least.*season.*point/i, /low.*season.*point/i],
  },
];

const _resolveAwardRule = (title) => {
  const normalized = String(title || '').trim();
  if (!normalized) return null;
  return AWARD_DISPLAY_RULES.find((rule) => rule.patterns.some((pattern) => pattern.test(normalized))) || null;
};

const _awardValueLabel = (record) => {
  if (!record) return '';
  const candidates = [record.points_total, record.points, record.value, record.record_value, record.score];
  const first = candidates.find((v) => v !== undefined && v !== null && String(v).trim() !== '');
  return first !== undefined ? String(first) : '';
};

const _extractTeamAndStartStatus = (value) => {
  const raw = String(value || '').trim();
  if (!raw) {
    return {
      team: '-',
      startedCode: '-',
      startedLabel: 'Unknown',
    };
  }

  const match = raw.match(/^(.*?)\s*-\s*(S|NS|TS)$/i);
  if (!match) {
    return {
      team: raw,
      startedCode: '-',
      startedLabel: 'Unknown',
    };
  }

  const code = String(match[2] || '').toUpperCase();
  let startedLabel = 'Unknown';
  if (code === 'S') startedLabel = 'Started';
  if (code === 'NS') startedLabel = 'Not Started';
  if (code === 'TS') startedLabel = 'Taxi Squad';

  return {
    team: String(match[1] || '').trim() || '-',
    startedCode: code,
    startedLabel,
  };
};

const _normalizeOwnerMatchKey = (value) =>
  String(value || '')
    .toLowerCase()
    .replace(/\s*-\s*(ns|s|ts)$/i, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

const HISTORY_SECTIONS = [
  { key: 'historical-analytics', label: 'Historical Analytics' },
  { key: 'champions', label: 'Champions + Awards' },
  { key: 'franchise-records', label: 'Franchise Records' },
  { key: 'player-records', label: 'Player Records' },
  { key: 'match-records', label: 'Match Records' },
  { key: 'all-time-series-records', label: 'All-Time Series Records' },
  { key: 'season-records', label: 'Season Records' },
  { key: 'career-records', label: 'Career Records' },
  { key: 'record-streaks', label: 'Record Streaks' },
];

const SECTION_TEXT = {
  'historical-analytics': {
    title: 'Historical Analytics',
    detail: 'Archive of historical draft results and past season analytics.',
  },
  champions: {
    title: 'League Champions + Awards',
    detail: 'Season champions and historical award honors in one consolidated view.',
  },
  awards: {
    title: 'League Champions + Awards',
    detail: 'Season champions and historical award honors in one consolidated view.',
  },
  'franchise-records': {
    title: 'Franchise Records',
    detail: 'Best single-game franchise scores.',
  },
  'player-records': {
    title: 'Player Records',
    detail: 'Best individual player weekly performances.',
  },
  'match-records': {
    title: 'Match Records',
    detail: 'Highest-scoring matchups and notable results.',
  },
  'all-time-series-records': {
    title: 'All-Time Series Records',
    detail: 'Head-to-head records between managers.',
  },
  'season-records': {
    title: 'Season Records',
    detail: 'Best season records and historical standings.',
  },
  'career-records': {
    title: 'Career Records',
    detail: 'Franchise career aggregate records.',
  },
  'record-streaks': {
    title: 'Record Streaks',
    detail: 'Notable win/loss streaks throughout history.',
  },
};

export default function LeagueHistory({ sectionKey }) {
  const leagueId = useActiveLeague();
  const normalizedSectionKey = sectionKey === 'awards' ? 'champions' : sectionKey;
  const [championsYear, setChampionsYear] = useState('');
  
  // Draft archive specific
  const [archiveSeasonOptions, setArchiveSeasonOptions] = useState([]);
  const [archiveYear, setArchiveYear] = useState('');
  const [archiveHistory, setArchiveHistory] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState('');
  const [archiveIncludeKeepers, setArchiveIncludeKeepers] = useState(false);
  
  // Historical records
  const [records, setRecords] = useState([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsError, setRecordsError] = useState('');
  const [championRecords, setChampionRecords] = useState([]);
  const [awardRecords, setAwardRecords] = useState([]);
  const [owners, setOwners] = useState([]);

  const [franchiseYearFilter, setFranchiseYearFilter] = useState('ALL');
  const [selectedFranchiseTeams, setSelectedFranchiseTeams] = useState([]);

  const [playerSearchTerm, setPlayerSearchTerm] = useState('');
  const [playerSortKey, setPlayerSortKey] = useState('points');
  const [playerSortDirection, setPlayerSortDirection] = useState('desc');
  const [playerViewMode, setPlayerViewMode] = useState('table');
  const [playerBarLimit, setPlayerBarLimit] = useState(20);

  const [matchSearchTerm, setMatchSearchTerm] = useState('');
  const [matchViewMode, setMatchViewMode] = useState('table');
  const [matchTeamFilter, setMatchTeamFilter] = useState('ALL');
  const [matchOwnerFilter, setMatchOwnerFilter] = useState('ALL');
  const [matchYearFilter, setMatchYearFilter] = useState('ALL');
  const [matchBarLimit, setMatchBarLimit] = useState(15);
  const [matchSortKey, setMatchSortKey] = useState('combined');
  const [matchSortDirection, setMatchSortDirection] = useState('desc');

  const [seriesSearchTerm, setSeriesSearchTerm] = useState('');
  const [seriesSortKey, setSeriesSortKey] = useState('totalPct');
  const [seriesSortDirection, setSeriesSortDirection] = useState('desc');

  const ownerNameById = useMemo(() => {
    const index = {};
    owners.forEach((owner) => {
      index[Number(owner.id)] = owner.team_name || owner.username || `Owner ${owner.id}`;
    });
    return index;
  }, [owners]);

  const ownerNameByTeamKey = useMemo(() => {
    const index = {};
    owners.forEach((owner) => {
      const ownerLabel = owner.username || owner.team_name || `Owner ${owner.id}`;
      const keys = [owner.team_name, owner.username].map(_normalizeOwnerMatchKey).filter(Boolean);
      keys.forEach((key) => {
        if (!index[key]) {
          index[key] = ownerLabel;
        }
      });
    });
    return index;
  }, [owners]);

  const championYearOptions = useMemo(() => {
    if (normalizedSectionKey !== 'champions') return [];
    const uniqueYears = new Set(
      championRecords
        .map((rec) => rec.champion_season ?? rec.season)
        .filter((value) => value !== null && value !== undefined && value !== '')
        .map((value) => String(value))
    );
    return [...uniqueYears].sort((a, b) => Number(b) - Number(a));
  }, [championRecords, normalizedSectionKey]);

  const championPlaceSlots = useMemo(() => {
    if (normalizedSectionKey !== 'champions') return [];
    return CHAMPION_TOP_PLACE_RANKS;
  }, [normalizedSectionKey]);

  const championRecordsByPlace = useMemo(() => {
    if (normalizedSectionKey !== 'champions' || !championsYear) return {};
    const recordsForYear = championRecords.filter(
      (rec) => String(rec.champion_season ?? rec.season) === championsYear
    );
    const byPlace = {};
    recordsForYear.forEach((rec) => {
      const place = Number(rec.place_rank);
      if (!Number.isInteger(place) || place < 1 || byPlace[place]) return;
      byPlace[place] = rec;
    });
    return byPlace;
  }, [championRecords, championsYear, normalizedSectionKey]);

  const awardsForSelectedChampionYear = useMemo(() => {
    if (normalizedSectionKey !== 'champions' || !championsYear) return [];
    const recordsForYear = awardRecords.filter(
      (rec) => String(rec.award_season ?? rec.season) === championsYear
    );

    const selected = {};
    recordsForYear.forEach((rec) => {
      const rule = _resolveAwardRule(rec.award_title || rec.title || rec.record_title);
      if (!rule) return;
      if (!selected[rule.key]) {
        selected[rule.key] = rec;
      }
    });

    return AWARD_DISPLAY_RULES.map((rule) => ({
      key: rule.key,
      label: rule.label,
      record: selected[rule.key] || null,
    }));
  }, [awardRecords, championsYear, normalizedSectionKey]);

  useEffect(() => {
    if (normalizedSectionKey !== 'champions') return;
    if (!championYearOptions.length) {
      setChampionsYear('');
      return;
    }
    if (!championYearOptions.includes(championsYear)) {
      setChampionsYear(championYearOptions[0]);
    }
  }, [normalizedSectionKey, championYearOptions, championsYear]);

  // Load owners and draft seasons once
  useEffect(() => {
    if (!leagueId) return;

    apiClient
      .get(`/leagues/owners?league_id=${Number(leagueId)}`)
      .then((res) => setOwners(Array.isArray(res.data) ? res.data : []))
      .catch(() => setOwners([]));

    apiClient
      .get(`/draft/seasons?league_id=${Number(leagueId)}`)
      .then((res) => {
        const seasons = Array.isArray(res.data)
          ? res.data
              .filter((year) => Number.isInteger(Number(year)))
              .map((year) => Number(year))
          : [];
        setArchiveSeasonOptions(seasons);
        if (seasons.length > 0) {
          setArchiveYear(String(seasons[0]));
        }
      })
      .catch(() => {
        setArchiveSeasonOptions([]);
        setArchiveYear('');
      });
  }, [leagueId]);

  // Load draft archive when section changes
  const loadArchive = async (id, year, includeKeepers) => {
    setArchiveLoading(true);
    try {
      const response = await apiClient.get(
        `/draft/history/by-year?league_id=${Number(id)}&year=${Number(year)}&include_keepers=${includeKeepers ? 'true' : 'false'}`
      );
      setArchiveHistory(Array.isArray(response.data) ? response.data : []);
      setArchiveError('');
    } catch {
      setArchiveHistory([]);
      setArchiveError('Unable to load archive results for that season.');
    } finally {
      setArchiveLoading(false);
    }
  };

  const openGeminiHistoryAssistant = (query = '') => {
    window.dispatchEvent(
      new CustomEvent('ffpi:open-advisor', {
        detail: {
          query,
        },
      })
    );
  };

  useEffect(() => {
    if (!leagueId || !archiveYear || normalizedSectionKey !== 'historical-analytics') return;
    loadArchive(leagueId, archiveYear, archiveIncludeKeepers);
  }, [leagueId, archiveYear, archiveIncludeKeepers, normalizedSectionKey]);

  const RECORDS_ENDPOINT_MAP = {
    'franchise-records': 'records/franchise',
    'player-records': 'records/player',
    'match-records': 'records/match',
    'all-time-series-records': 'records/all-time-series',
    'career-records': 'records/career',
    'record-streaks': 'records/streaks',
  };

  // Load historical records based on section key
  const loadRecords = async (id, key) => {
    if (key === 'champions') {
      setRecordsLoading(true);
      try {
        const [championsResponse, awardsResponse] = await Promise.all([
          apiClient.get(`/leagues/${Number(id)}/history/champions`),
          apiClient.get(`/leagues/${Number(id)}/history/awards`),
        ]);
        setChampionRecords(championsResponse.data?.records || []);
        setAwardRecords(awardsResponse.data?.records || []);
        setRecords([]);
        setRecordsError('');
      } catch {
        setChampionRecords([]);
        setAwardRecords([]);
        setRecords([]);
        setRecordsError('Unable to load champions and awards history.');
      } finally {
        setRecordsLoading(false);
      }
      return;
    }

    const endpoint = RECORDS_ENDPOINT_MAP[key];
    if (!endpoint) return;
    setRecordsLoading(true);
    try {
      const response = await apiClient.get(`/leagues/${Number(id)}/history/${endpoint}`);
      setRecords(response.data?.records || []);
      setChampionRecords([]);
      setAwardRecords([]);
      setRecordsError('');
    } catch {
      setRecords([]);
      setChampionRecords([]);
      setAwardRecords([]);
      setRecordsError(`Unable to load ${SECTION_TEXT[key].title.toLowerCase()}.`);
    } finally {
      setRecordsLoading(false);
    }
  };

  useEffect(() => {
    if (!leagueId || normalizedSectionKey === 'historical-analytics' || normalizedSectionKey === 'season-records') return;
    loadRecords(leagueId, normalizedSectionKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId, normalizedSectionKey]);

  const franchiseRows = useMemo(
    () =>
      records
        .map((rec) => {
          const sourceTeam = rec.franchise_name_clean || 'Unknown';
          const ownerFromId =
            ownerNameById[Number(rec.owner_id)] ||
            ownerNameById[Number(rec.team_owner_id)] ||
            null;
          const ownerFromTeamName =
            ownerNameByTeamKey[_normalizeOwnerMatchKey(sourceTeam)] ||
            ownerNameByTeamKey[_normalizeOwnerMatchKey(rec.owner_context_raw)] ||
            null;

          return {
            sourceTeam,
            ownerLabel: ownerFromId || ownerFromTeamName || sourceTeam,
            year: Number(rec.record_year),
            week: Number(rec.record_week),
            points: Number(rec.points || 0),
          };
        })
        .filter((row) => Number.isFinite(row.year) && Number.isFinite(row.points)),
    [records, ownerNameById, ownerNameByTeamKey]
  );

  const franchiseYearOptions = useMemo(
    () => [...new Set(franchiseRows.map((row) => row.year))].sort((a, b) => b - a),
    [franchiseRows]
  );

  const franchiseTeamOptions = useMemo(
    () => [...new Set(franchiseRows.map((row) => row.ownerLabel))].sort((a, b) => a.localeCompare(b)),
    [franchiseRows]
  );

  useEffect(() => {
    if (normalizedSectionKey !== 'franchise-records') return;
    if (!franchiseYearOptions.length) {
      setFranchiseYearFilter('ALL');
    }
  }, [normalizedSectionKey, franchiseYearOptions]);

  useEffect(() => {
    if (normalizedSectionKey !== 'franchise-records') return;
    if (!franchiseTeamOptions.length) {
      setSelectedFranchiseTeams([]);
      return;
    }
    if (!selectedFranchiseTeams.length) {
      setSelectedFranchiseTeams(franchiseTeamOptions.slice(0, Math.min(4, franchiseTeamOptions.length)));
      return;
    }
    setSelectedFranchiseTeams((prev) => prev.filter((team) => franchiseTeamOptions.includes(team)));
  }, [normalizedSectionKey, franchiseTeamOptions, selectedFranchiseTeams.length]);

  const franchiseChartRows = useMemo(() => {
    let nextRows = franchiseRows;
    if (franchiseYearFilter !== 'ALL') {
      nextRows = nextRows.filter((row) => String(row.year) === franchiseYearFilter);
    }
    if (selectedFranchiseTeams.length) {
      nextRows = nextRows.filter((row) => selectedFranchiseTeams.includes(row.ownerLabel));
    }
    return nextRows;
  }, [franchiseRows, franchiseYearFilter, selectedFranchiseTeams]);

  const franchiseChartConfig = useMemo(() => {
    const showAllYears = franchiseYearFilter === 'ALL';
    const labels = showAllYears
      ? [...new Set(franchiseChartRows.map((row) => String(row.year)))].sort((a, b) => Number(a) - Number(b))
      : [...new Set(franchiseChartRows.map((row) => String(row.week)))].sort((a, b) => Number(a) - Number(b));

    const datasets = selectedFranchiseTeams.map((team, idx) => {
      const teamRows = franchiseChartRows.filter((row) => row.ownerLabel === team);
      const meta = labels.map((label) => {
        const matching = showAllYears
          ? teamRows.filter((row) => String(row.year) === label)
          : teamRows.filter((row) => String(row.week) === label);
        if (!matching.length) return null;
        const best = matching.reduce((top, row) => (row.points > top.points ? row : top), matching[0]);
        return best;
      });

      return {
        label: team,
        data: meta.map((row) => (row ? row.points : null)),
        borderColor: CHART_PALETTE[idx % CHART_PALETTE.length],
        backgroundColor: CHART_PALETTE[idx % CHART_PALETTE.length],
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.25,
        spanGaps: true,
        meta,
      };
    });

    return {
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              title: (items) => {
                const value = items[0]?.label;
                return showAllYears ? `Year ${value}` : `Week ${value}`;
              },
              label: (context) => {
                const meta = context.dataset.meta?.[context.dataIndex];
                if (!meta) return `${context.dataset.label}: No score`;
                return `${context.dataset.label}: ${Number(meta.points).toFixed(2)} pts (W${meta.week}, ${meta.year}) [${meta.sourceTeam}]`;
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: showAllYears ? 'Year' : 'Week',
            },
          },
          y: {
            title: {
              display: true,
              text: 'Points',
            },
          },
        },
      },
    };
  }, [franchiseYearFilter, franchiseChartRows, selectedFranchiseTeams]);

  const playerRecordRows = useMemo(() => {
    const deduped = new Map();

    records.forEach((rec) => {
      const ownerContext = _extractTeamAndStartStatus(rec.owner_context_raw);
      const ownerName =
        ownerNameByTeamKey[_normalizeOwnerMatchKey(ownerContext.team)] ||
        ownerNameByTeamKey[_normalizeOwnerMatchKey(rec.owner_context_raw)] ||
        '-';

      const row = {
        player: rec.player_name || 'Unknown',
        position: rec.position || '-',
        team: ownerContext.team,
        ownerName,
        startedCode: ownerContext.startedCode,
        started: ownerContext.startedLabel,
        week: Number(rec.record_week) || 0,
        year: Number(rec.record_year) || 0,
        points: Number(rec.points || 0),
      };

      // Source payload can include duplicate rows for the same player/week/season.
      const key = [
        rec.player_id ?? row.player,
        row.position,
        row.team,
        row.startedCode,
        row.week,
        row.year,
      ].join('|');

      const existing = deduped.get(key);
      if (!existing || row.points > existing.points) {
        deduped.set(key, row);
      }
    });

    return [...deduped.values()];
  }, [records, ownerNameByTeamKey]);

  const filteredPlayerRows = useMemo(() => {
    const query = playerSearchTerm.trim().toLowerCase();
    if (!query) return playerRecordRows;
    return playerRecordRows.filter((row) =>
      [
        row.player,
        row.position,
        row.team,
        row.ownerName,
        row.started,
        String(row.week),
        String(row.year),
        String(row.points),
      ]
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
  }, [playerRecordRows, playerSearchTerm]);

  const sortedPlayerRows = useMemo(() => {
    const rows = [...filteredPlayerRows];
    rows.sort((a, b) => {
      const numericKeys = new Set(['week', 'year', 'points']);
      if (numericKeys.has(playerSortKey)) {
        const delta = Number(a[playerSortKey]) - Number(b[playerSortKey]);
        return playerSortDirection === 'asc' ? delta : -delta;
      }
      const left = String(a[playerSortKey] || '');
      const right = String(b[playerSortKey] || '');
      const delta = left.localeCompare(right, undefined, { sensitivity: 'base' });
      return playerSortDirection === 'asc' ? delta : -delta;
    });
    return rows;
  }, [filteredPlayerRows, playerSortDirection, playerSortKey]);

  const playerBarConfig = useMemo(() => {
    const positionColors = {
      QB: '#22d3ee',
      RB: '#22c55e',
      WR: '#f59e0b',
      TE: '#a78bfa',
      K: '#f97316',
      DEF: '#64748b',
      '-': '#94a3b8',
    };

    const topRows = [...sortedPlayerRows].slice(0, Math.max(5, playerBarLimit));
    const labels = topRows.map((row) => row.player);
    const values = topRows.map((row) => row.points);
    const colors = topRows.map((row) => positionColors[row.position] || '#06b6d4');

    return {
      data: {
        labels,
        datasets: [
          {
            label: 'Top Player Single-Week Points',
            data: values,
            backgroundColor: colors,
            borderRadius: 6,
            meta: topRows,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const row = items[0]?.dataset?.meta?.[items[0]?.dataIndex || 0];
                if (!row) return items[0]?.label || '';
                return `${row.player} (${row.position})`;
              },
              label: (context) => {
                const row = context.dataset.meta?.[context.dataIndex];
                if (!row) return `${Number(context.raw).toFixed(2)} pts`;
                return `${Number(row.points).toFixed(2)} pts`;
              },
              afterLabel: (context) => {
                const row = context.dataset.meta?.[context.dataIndex];
                if (!row) return '';
                return [
                  `Owner: ${row.ownerName}`,
                  `Team: ${row.team}`,
                  `Started: ${row.started}`,
                  `Week/Year: W${row.week} ${row.year}`,
                ];
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Points',
            },
          },
          y: {
            title: {
              display: true,
              text: 'Player',
            },
          },
        },
        indexAxis: 'y',
      },
    };
  }, [playerBarLimit, sortedPlayerRows]);

  const matchRows = useMemo(
    () => {
      const deduped = new Map();
      records.forEach((rec) => {
        const awayTeam = rec.away_franchise_raw || rec.away_team || 'Unknown';
        const homeTeam = rec.home_franchise_raw || rec.home_team || 'Unknown';
        const awayScore = Number(rec.away_points ?? rec.away_score ?? 0) || 0;
        const homeScore = Number(rec.home_points ?? rec.home_score ?? 0) || 0;
        const week = Number(rec.record_week ?? rec.week ?? 0) || 0;
        const year = Number(rec.record_year ?? rec.season ?? rec.year ?? 0) || 0;
        const combined = Number(rec.combined_score ?? rec.combined ?? awayScore + homeScore) || 0;
        const awayOwner =
          rec.away_owner_name ||
          ownerNameByTeamKey[_normalizeOwnerMatchKey(awayTeam)] ||
          '-';
        const homeOwner =
          rec.home_owner_name ||
          ownerNameByTeamKey[_normalizeOwnerMatchKey(homeTeam)] ||
          '-';

        const row = {
          awayTeam,
          awayOwner,
          homeTeam,
          homeOwner,
          awayScore,
          homeScore,
          week,
          year,
          combined,
        };

        const key = [
          year,
          week,
          _normalizeOwnerMatchKey(awayTeam),
          _normalizeOwnerMatchKey(homeTeam),
          awayScore.toFixed(2),
          homeScore.toFixed(2),
          combined.toFixed(2),
        ].join('|');

        if (!deduped.has(key)) {
          deduped.set(key, row);
        }
      });

      return [...deduped.values()];
    },
    [records, ownerNameByTeamKey]
  );

  const matchYearOptions = useMemo(
    () => [...new Set(matchRows.map((row) => row.year).filter((year) => Number.isFinite(year) && year > 0))].sort((a, b) => b - a),
    [matchRows]
  );

  const matchTeamOptions = useMemo(() => {
    const teams = new Set();
    matchRows.forEach((row) => {
      if (row.awayTeam) teams.add(row.awayTeam);
      if (row.homeTeam) teams.add(row.homeTeam);
    });
    return [...teams].sort((a, b) => a.localeCompare(b));
  }, [matchRows]);

  const matchOwnerOptions = useMemo(() => {
    const ownersSet = new Set();
    matchRows.forEach((row) => {
      if (row.awayOwner && row.awayOwner !== '-') ownersSet.add(row.awayOwner);
      if (row.homeOwner && row.homeOwner !== '-') ownersSet.add(row.homeOwner);
    });
    return [...ownersSet].sort((a, b) => a.localeCompare(b));
  }, [matchRows]);

  const filteredMatchRows = useMemo(() => {
    const query = matchSearchTerm.trim().toLowerCase();
    return matchRows.filter((row) => {
      if (matchYearFilter !== 'ALL' && String(row.year) !== matchYearFilter) return false;
      if (matchTeamFilter !== 'ALL' && row.awayTeam !== matchTeamFilter && row.homeTeam !== matchTeamFilter) return false;
      if (matchOwnerFilter !== 'ALL' && row.awayOwner !== matchOwnerFilter && row.homeOwner !== matchOwnerFilter) return false;
      if (!query) return true;
      return [
        row.awayTeam,
        row.awayOwner,
        row.homeTeam,
        row.homeOwner,
        String(row.awayScore),
        String(row.homeScore),
        String(row.week),
        String(row.year),
        String(row.combined),
      ]
        .join(' ')
        .toLowerCase()
        .includes(query);
    });
  }, [matchOwnerFilter, matchRows, matchSearchTerm, matchTeamFilter, matchYearFilter]);

  const sortedMatchRows = useMemo(() => {
    const rows = [...filteredMatchRows];
    const numericKeys = new Set(['awayScore', 'homeScore', 'week', 'year', 'combined']);
    rows.sort((a, b) => {
      if (numericKeys.has(matchSortKey)) {
        const delta = Number(a[matchSortKey]) - Number(b[matchSortKey]);
        return matchSortDirection === 'asc' ? delta : -delta;
      }
      const delta = String(a[matchSortKey] || '').localeCompare(String(b[matchSortKey] || ''), undefined, {
        sensitivity: 'base',
      });
      return matchSortDirection === 'asc' ? delta : -delta;
    });
    return rows;
  }, [filteredMatchRows, matchSortDirection, matchSortKey]);

  const matchBarConfig = useMemo(() => {
    const topRows = [...sortedMatchRows]
      .sort((a, b) => b.combined - a.combined)
      .slice(0, Math.max(5, matchBarLimit));
    return {
      data: {
        labels: topRows.map((row) => `${row.awayTeam} vs ${row.homeTeam} (${row.year} W${row.week})`),
        datasets: [
          {
            label: 'Combined Match Points',
            data: topRows.map((row) => row.combined),
            backgroundColor: topRows.map((_, idx) => CHART_PALETTE[idx % CHART_PALETTE.length]),
            borderRadius: 6,
            meta: topRows,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                const row = context.dataset.meta?.[context.dataIndex];
                if (!row) return `${Number(context.raw).toFixed(2)} points`;
                return `${Number(row.combined).toFixed(2)} combined points`;
              },
              afterLabel: (context) => {
                const row = context.dataset.meta?.[context.dataIndex];
                if (!row) return '';
                return [
                  `Away: ${row.awayOwner} (${row.awayTeam}) - ${Number(row.awayScore).toFixed(2)}`,
                  `Home: ${row.homeOwner} (${row.homeTeam}) - ${Number(row.homeScore).toFixed(2)}`,
                ];
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Combined Points',
            },
          },
          y: {
            title: {
              display: true,
              text: 'Matchup',
            },
          },
        },
      },
    };
  }, [matchBarLimit, sortedMatchRows]);

  const seriesRows = useMemo(
    () =>
      records.map((rec) => ({
        perspectiveOwner: rec.perspective_owner_name || '-',
        perspectiveTeam: rec.perspective_team_name || '-',
        opponentOwner:
          rec.opponent_owner_name ||
          ownerNameByTeamKey[_normalizeOwnerMatchKey(rec.opponent_team_name || rec.opponent_franchise_raw)] ||
          '-',
        opponentTeam: rec.opponent_team_name || rec.opponent_franchise_raw || 'Unknown',
        season: rec.series_season ?? rec.record_year ?? '-',
        seasonRecord: rec.season_w_l_t_raw || '-',
        totalRecord: rec.total_w_l_t_raw || '-',
        totalPct: Number(rec.total_pct || 0),
      })),
    [ownerNameByTeamKey, records]
  );

  const filteredSeriesRows = useMemo(() => {
    const query = seriesSearchTerm.trim().toLowerCase();
    if (!query) return seriesRows;
    return seriesRows.filter((row) =>
      [
        row.perspectiveOwner,
        row.perspectiveTeam,
        row.opponentOwner,
        row.opponentTeam,
        String(row.season),
        row.seasonRecord,
        row.totalRecord,
        String(row.totalPct),
      ]
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
  }, [seriesRows, seriesSearchTerm]);

  const sortedSeriesRows = useMemo(() => {
    const rows = [...filteredSeriesRows];
    const numericKeys = new Set(['totalPct', 'season']);
    rows.sort((a, b) => {
      if (numericKeys.has(seriesSortKey)) {
        const delta = Number(a[seriesSortKey]) - Number(b[seriesSortKey]);
        return seriesSortDirection === 'asc' ? delta : -delta;
      }
      const delta = String(a[seriesSortKey] || '').localeCompare(String(b[seriesSortKey] || ''), undefined, {
        sensitivity: 'base',
      });
      return seriesSortDirection === 'asc' ? delta : -delta;
    });
    return rows;
  }, [filteredSeriesRows, seriesSortDirection, seriesSortKey]);

  const active = SECTION_TEXT[normalizedSectionKey] || SECTION_TEXT['historical-analytics'];

  return (
    <PageTemplate
      title="League History"
      subtitle="Historical and legacy league insights, separated from current-season workflows."
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {HISTORY_SECTIONS.map((section) => (
          <Link
            key={section.key}
            to={`/league-history/${section.key}`}
            className={`rounded-xl border px-4 py-3 text-sm font-semibold transition ${
              section.key === normalizedSectionKey
                ? 'border-cyan-500 bg-cyan-50 text-cyan-800 dark:border-cyan-500 dark:bg-slate-800 dark:text-cyan-300'
                : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800'
            }`}
          >
            {section.label}
          </Link>
        ))}
      </div>

      <section className={cardSurface}>
        <h2 className="text-lg font-black uppercase tracking-wider text-slate-900 dark:text-white">
          {active.title}
        </h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{active.detail}</p>

        {/* HISTORICAL ANALYTICS - Draft Archive */}
        {normalizedSectionKey === 'historical-analytics' && (
          <div className="mt-4 rounded-lg border border-slate-300 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-800 dark:text-slate-200">
                <FiBarChart2 className="inline mr-2" />
                Historical Draft Archive
              </h3>
              <div className="flex items-center gap-2">
                <label className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Season
                </label>
                <select
                  value={archiveYear}
                  onChange={(event) => {
                    setArchiveYear(event.target.value);
                  }}
                  className="rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  disabled={archiveSeasonOptions.length === 0}
                >
                  {archiveSeasonOptions.length === 0 ? (
                    <option value="">No seasons available</option>
                  ) : (
                    archiveSeasonOptions.map((season) => (
                      <option key={season} value={season}>
                        {season}
                      </option>
                    ))
                  )}
                </select>
                <label className="ml-2 flex items-center gap-1 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <input
                    type="checkbox"
                    checked={archiveIncludeKeepers}
                    onChange={(event) => setArchiveIncludeKeepers(event.target.checked)}
                    className="h-3 w-3 rounded border border-slate-300 bg-white text-cyan-600 dark:border-slate-700 dark:bg-slate-800"
                  />
                  Include Keepers
                </label>
              </div>
            </div>

            {archiveLoading ? (
              <LoadingState message="Loading draft archive..." />
            ) : archiveError ? (
              <EmptyState message={archiveError} />
            ) : archiveYear && archiveHistory.length === 0 ? (
              <EmptyState message={`No archived draft picks found for ${archiveYear}.`} />
            ) : archiveHistory.length > 0 ? (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'owner', label: 'Team / Owner' },
                      { key: 'player', label: 'Player' },
                      { key: 'amount', label: 'Amount', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {archiveHistory.map((pick) => (
                        <StandardTableRow key={pick.id || `${pick.player_id}-${pick.timestamp}`}>
                          <td className={tableCell}>
                            {ownerNameById[Number(pick.owner_id)] || `Owner ${pick.owner_id}`}
                          </td>
                          <td className={tableCell}>{pick.player_name || 'Unknown Player'}</td>
                          <td className={tableCellNumeric}>${Number(pick.amount || 0)}</td>
                        </StandardTableRow>
                      ))}
                  </tbody>
                </StandardTable>
              </div>
            ) : null}

            <div className="mt-4 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                Historical Team-Owner Mapping
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Historical owner mapping now lives in a dedicated commissioner utility so this page stays focused on read-only league history.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Link
                  to="/commissioner/history-owner-mapping"
                  className="rounded bg-cyan-600 px-3 py-1 text-xs font-semibold text-white"
                >
                  Open Mapping Utility
                </Link>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Commissioner-only route. Stored mappings still power all-time series and match record owner labels.
                </span>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                Gemini History Assistant
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Historical questions now run through the Gemini assistant instead of a separate page-level beta tool.
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="rounded bg-cyan-600 px-3 py-1 text-xs font-semibold text-white disabled:opacity-60"
                  onClick={() => openGeminiHistoryAssistant('Who was the champion in 2021?')}
                >
                  Open Gemini for champions
                </button>
                <button
                  type="button"
                  className="rounded border border-cyan-600 px-3 py-1 text-xs font-semibold text-cyan-600 dark:text-cyan-300"
                  onClick={() => openGeminiHistoryAssistant('What was the highest scoring game in 2019?')}
                >
                  Open Gemini for matchup records
                </button>
              </div>
            </div>
          </div>
        )}

        {/* SEASON RECORDS - Playoff Brackets */}
        {normalizedSectionKey === 'season-records' && (
          <div className="mt-4 rounded-lg border border-slate-300 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-800 dark:text-slate-200">
              <FiTrendingUp className="inline mr-2" />
              Historical Playoff Brackets
            </h3>
            <BracketAccordion
              leagueId={leagueId}
              showHistoricalToggle={false}
              historicalOnly
            />
          </div>
        )}

        {/* CHAMPIONS */}
        {normalizedSectionKey === 'champions' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading league champions..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : championRecords.length === 0 && awardRecords.length === 0 ? (
              <EmptyState message="No champion or award records found." />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                    Season Snapshot
                  </p>
                  <div className="flex items-center gap-2">
                    <label className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      Year
                    </label>
                    <select
                      value={championsYear}
                      onChange={(event) => setChampionsYear(event.target.value)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                      {championYearOptions.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {championPlaceSlots.map((place) => {
                    const rec = championRecordsByPlace[place];
                    const isChampion = place === 1;
                    return (
                      <div
                        key={place}
                        className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900"
                      >
                        <div className="mb-2 flex items-center justify-between">
                          <p className="font-bold text-slate-900 dark:text-white">
                            Place {place}
                          </p>
                          <FiAward className={`text-xl ${isChampion ? 'text-amber-500' : 'text-slate-400 dark:text-slate-500'}`} />
                        </div>
                        {rec ? (
                          <p className="text-sm text-slate-700 dark:text-slate-300">
                            {rec.franchise_name_clean || 'Unknown'} {isChampion ? '(Champion)' : ''}
                          </p>
                        ) : (
                          <p className="text-sm italic text-slate-500 dark:text-slate-400">No record</p>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <p className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-200">Awards ({championsYear || 'Season'})</p>
                  {awardsForSelectedChampionYear.length === 0 ? (
                    <p className="text-sm italic text-slate-500 dark:text-slate-400">No awards recorded for this season.</p>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      {awardsForSelectedChampionYear.map((award) => (
                        <div key={award.key} className="rounded border border-slate-200 px-3 py-2 dark:border-slate-700">
                          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{award.label}</p>
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                            {award.record?.franchise_name_clean || 'No record'}
                          </p>
                          {award.record && _awardValueLabel(award.record) ? (
                            <p className="text-xs text-slate-500 dark:text-slate-400">{_awardValueLabel(award.record)}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Showing season {championsYear}. Empty boxes indicate no stored finish for that place/year.
                </p>
              </div>
            )}
          </div>
        )}

        {/* FRANCHISE RECORDS */}
        {normalizedSectionKey === 'franchise-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading franchise records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No franchise records found." />
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <div className="flex items-center gap-2">
                    <label className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Year</label>
                    <select
                      value={franchiseYearFilter}
                      onChange={(event) => setFranchiseYearFilter(event.target.value)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                      <option value="ALL">All Years</option>
                      {franchiseYearOptions.map((year) => (
                        <option key={year} value={String(year)}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Owners</p>
                    {franchiseTeamOptions.map((team) => {
                      const selected = selectedFranchiseTeams.includes(team);
                      return (
                        <button
                          type="button"
                          key={team}
                          onClick={() => {
                            setSelectedFranchiseTeams((prev) =>
                              prev.includes(team) ? prev.filter((item) => item !== team) : [...prev, team]
                            );
                          }}
                          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                            selected
                              ? 'border-cyan-500 bg-cyan-100 text-cyan-900 dark:border-cyan-400 dark:bg-cyan-900/30 dark:text-cyan-200'
                              : 'border-slate-300 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}
                        >
                          {team}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="h-[360px] rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  {franchiseChartConfig.data.datasets.length === 0 ? (
                    <div className="flex h-full items-center justify-center text-sm text-slate-500 dark:text-slate-400">
                      Select at least one owner to render the graph.
                    </div>
                  ) : (
                    <Line data={franchiseChartConfig.data} options={franchiseChartConfig.options} />
                  )}
                </div>

                <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                  <StandardTable>
                    <StandardTableHead
                      headers={[
                        { key: 'franchise', label: 'Owner' },
                        { key: 'source', label: 'Source Franchise' },
                        { key: 'year', label: 'Year' },
                        { key: 'week', label: 'Week' },
                        { key: 'points', label: 'Points', className: 'text-right' },
                      ]}
                    />
                    <tbody>
                      {franchiseChartRows.map((row, idx) => (
                        <StandardTableRow key={`${row.ownerLabel}-${row.year}-${row.week}-${idx}`}>
                          <td className={tableCell}>{row.ownerLabel}</td>
                          <td className={tableCell}>{row.sourceTeam}</td>
                          <td className={tableCell}>{row.year}</td>
                          <td className={tableCell}>Week {row.week}</td>
                          <td className={tableCellNumeric}>{row.points.toFixed(2)}</td>
                        </StandardTableRow>
                      ))}
                    </tbody>
                  </StandardTable>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PLAYER RECORDS */}
        {normalizedSectionKey === 'player-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading player records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No player records found." />
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setPlayerViewMode('table')}
                      className={`rounded px-3 py-1 text-xs font-semibold ${
                        playerViewMode === 'table'
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                      }`}
                    >
                      Table View
                    </button>
                    <button
                      type="button"
                      onClick={() => setPlayerViewMode('bar')}
                      className={`rounded px-3 py-1 text-xs font-semibold ${
                        playerViewMode === 'bar'
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                      }`}
                    >
                      Bar Graph
                    </button>
                  </div>
                  <input
                    value={playerSearchTerm}
                    onChange={(event) => setPlayerSearchTerm(event.target.value)}
                    placeholder="Search player, position, owner, team, started, week, year"
                    className="w-full rounded border border-slate-300 bg-white px-3 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white md:w-96"
                  />
                </div>

                {playerViewMode === 'bar' ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                        Players shown
                      </label>
                      <select
                        value={playerBarLimit}
                        onChange={(event) => setPlayerBarLimit(Number(event.target.value) || 20)}
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      >
                        {[10, 15, 20, 25, 30, 40, 50].map((count) => (
                          <option key={count} value={count}>
                            Top {count}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="h-[340px] rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                      <Bar data={playerBarConfig.data} options={playerBarConfig.options} />
                    </div>
                  </div>
                ) : (
                  <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                    <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                      <thead className="bg-slate-100 dark:bg-slate-800">
                        <tr>
                          {[
                            { key: 'player', label: 'Player' },
                            { key: 'position', label: 'Position' },
                            { key: 'ownerName', label: 'Owner' },
                            { key: 'team', label: 'Team' },
                            { key: 'started', label: 'Started' },
                            { key: 'week', label: 'Week' },
                            { key: 'year', label: 'Year' },
                            { key: 'points', label: 'Points' },
                          ].map((column) => (
                            <th key={column.key} className="px-3 py-2 text-left font-semibold text-slate-700 dark:text-slate-200">
                              <button
                                type="button"
                                onClick={() => {
                                  if (playerSortKey === column.key) {
                                    setPlayerSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
                                  } else {
                                    setPlayerSortKey(column.key);
                                    setPlayerSortDirection(column.key === 'points' ? 'desc' : 'asc');
                                  }
                                }}
                                className="inline-flex items-center gap-1"
                              >
                                {column.label}
                                {playerSortKey === column.key ? (playerSortDirection === 'asc' ? '↑' : '↓') : ''}
                              </button>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                        {sortedPlayerRows.map((row, idx) => (
                          <tr key={`${row.player}-${row.week}-${row.year}-${idx}`} className="bg-white dark:bg-slate-900">
                            <td className={tableCell}>{row.player}</td>
                            <td className={tableCell}>{row.position}</td>
                            <td className={tableCell}>{row.ownerName}</td>
                            <td className={tableCell}>{row.team}</td>
                            <td className={tableCell}>{row.started}</td>
                            <td className={tableCell}>{row.week}</td>
                            <td className={tableCell}>{row.year}</td>
                            <td className={tableCellNumeric}>{Number(row.points).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* MATCH RECORDS */}
        {normalizedSectionKey === 'match-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading matchup records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No matchup records found." />
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setMatchViewMode('table')}
                      className={`rounded px-3 py-1 text-xs font-semibold ${
                        matchViewMode === 'table'
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                      }`}
                    >
                      Table View
                    </button>
                    <button
                      type="button"
                      onClick={() => setMatchViewMode('bar')}
                      className={`rounded px-3 py-1 text-xs font-semibold ${
                        matchViewMode === 'bar'
                          ? 'bg-cyan-600 text-white'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200'
                      }`}
                    >
                      Bar Graph
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={matchYearFilter}
                      onChange={(event) => setMatchYearFilter(event.target.value)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                      <option value="ALL">All Years</option>
                      {matchYearOptions.map((year) => (
                        <option key={year} value={String(year)}>
                          {year}
                        </option>
                      ))}
                    </select>

                    <select
                      value={matchTeamFilter}
                      onChange={(event) => setMatchTeamFilter(event.target.value)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                      <option value="ALL">All Teams</option>
                      {matchTeamOptions.map((team) => (
                        <option key={team} value={team}>
                          {team}
                        </option>
                      ))}
                    </select>

                    <select
                      value={matchOwnerFilter}
                      onChange={(event) => setMatchOwnerFilter(event.target.value)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    >
                      <option value="ALL">All Owners</option>
                      {matchOwnerOptions.map((owner) => (
                        <option key={owner} value={owner}>
                          {owner}
                        </option>
                      ))}
                    </select>
                  </div>

                  <input
                    value={matchSearchTerm}
                    onChange={(event) => setMatchSearchTerm(event.target.value)}
                    placeholder="Search teams, owners, week, year, scores"
                    className="w-full rounded border border-slate-300 bg-white px-3 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white md:w-96"
                  />
                </div>

                {matchViewMode === 'bar' ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                        Matchups shown
                      </label>
                      <select
                        value={matchBarLimit}
                        onChange={(event) => setMatchBarLimit(Number(event.target.value) || 15)}
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      >
                        {[10, 15, 20, 25, 30, 40].map((count) => (
                          <option key={count} value={count}>
                            Top {count}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="h-[340px] rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                      <Bar data={matchBarConfig.data} options={matchBarConfig.options} />
                    </div>
                  </div>
                ) : (
                  <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                    <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                      <thead className="bg-slate-100 dark:bg-slate-800">
                        <tr>
                          {[
                            { key: 'year', label: 'Year' },
                            { key: 'week', label: 'Week' },
                            { key: 'awayOwner', label: 'Away Owner' },
                            { key: 'awayTeam', label: 'Away Team' },
                            { key: 'awayScore', label: 'Away Score' },
                            { key: 'homeOwner', label: 'Home Owner' },
                            { key: 'homeTeam', label: 'Home Team' },
                            { key: 'homeScore', label: 'Home Score' },
                            { key: 'combined', label: 'Combined' },
                          ].map((column) => (
                            <th key={column.key} className="px-3 py-2 text-left font-semibold text-slate-700 dark:text-slate-200">
                              <button
                                type="button"
                                onClick={() => {
                                  if (matchSortKey === column.key) {
                                    setMatchSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
                                  } else {
                                    setMatchSortKey(column.key);
                                    setMatchSortDirection(
                                      ['awayScore', 'homeScore', 'combined', 'week', 'year'].includes(column.key)
                                        ? 'desc'
                                        : 'asc'
                                    );
                                  }
                                }}
                                className="inline-flex items-center gap-1"
                              >
                                {column.label}
                                {matchSortKey === column.key ? (matchSortDirection === 'asc' ? '↑' : '↓') : ''}
                              </button>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                        {sortedMatchRows.map((row, idx) => (
                          <tr key={`${row.awayTeam}-${row.homeTeam}-${row.year}-${row.week}-${idx}`} className="bg-white dark:bg-slate-900">
                            <td className={tableCell}>{row.year}</td>
                            <td className={tableCell}>{row.week}</td>
                            <td className={tableCell}>{row.awayOwner}</td>
                            <td className={tableCell}>{row.awayTeam}</td>
                            <td className={tableCellNumeric}>{Number(row.awayScore).toFixed(2)}</td>
                            <td className={tableCell}>{row.homeOwner}</td>
                            <td className={tableCell}>{row.homeTeam}</td>
                            <td className={tableCellNumeric}>{Number(row.homeScore).toFixed(2)}</td>
                            <td className={tableCellNumeric}>{Number(row.combined).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ALL-TIME SERIES RECORDS */}
        {normalizedSectionKey === 'all-time-series-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading all-time series records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No series records found." />
            ) : (
              <div className="space-y-3">
                <div className="rounded border border-slate-300 bg-white px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                  <span className="font-semibold">How to read this:</span> each row is from the listed <span className="font-semibold">Perspective Owner/Team</span> versus the listed <span className="font-semibold">Opponent Owner/Team</span>.
                </div>

                <input
                  value={seriesSearchTerm}
                  onChange={(event) => setSeriesSearchTerm(event.target.value)}
                  placeholder="Search owner, team, opponent, season, records"
                  className="w-full rounded border border-slate-300 bg-white px-3 py-1 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white md:w-96"
                />

                <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                  <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
                    <thead className="bg-slate-100 dark:bg-slate-800">
                      <tr>
                        {[
                          { key: 'perspectiveOwner', label: 'Perspective Owner' },
                          { key: 'perspectiveTeam', label: 'Perspective Team' },
                          { key: 'opponentOwner', label: 'Opponent Owner' },
                          { key: 'opponentTeam', label: 'Opponent Team' },
                          { key: 'season', label: 'Season' },
                          { key: 'seasonRecord', label: 'Season Record' },
                          { key: 'totalRecord', label: 'All-Time Record' },
                          { key: 'totalPct', label: 'Win %' },
                        ].map((column) => (
                          <th key={column.key} className="px-3 py-2 text-left font-semibold text-slate-700 dark:text-slate-200">
                            <button
                              type="button"
                              onClick={() => {
                                if (seriesSortKey === column.key) {
                                  setSeriesSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
                                } else {
                                  setSeriesSortKey(column.key);
                                  setSeriesSortDirection(column.key === 'totalPct' ? 'desc' : 'asc');
                                }
                              }}
                              className="inline-flex items-center gap-1"
                            >
                              {column.label}
                              {seriesSortKey === column.key ? (seriesSortDirection === 'asc' ? '↑' : '↓') : ''}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {sortedSeriesRows.map((row, idx) => (
                        <tr key={`${row.perspectiveOwner}-${row.opponentTeam}-${row.season}-${idx}`} className="bg-white dark:bg-slate-900">
                          <td className={tableCell}>{row.perspectiveOwner}</td>
                          <td className={tableCell}>{row.perspectiveTeam}</td>
                          <td className={tableCell}>{row.opponentOwner}</td>
                          <td className={tableCell}>{row.opponentTeam}</td>
                          <td className={tableCell}>{row.season}</td>
                          <td className={tableCell}>{row.seasonRecord}</td>
                          <td className={tableCell}>{row.totalRecord}</td>
                          <td className={tableCellNumeric}>{Number(row.totalPct).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CAREER RECORDS */}
        {normalizedSectionKey === 'career-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading career records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No career records found." />
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'franchise', label: 'Franchise' },
                      { key: 'record', label: 'Record' },
                      { key: 'pf', label: 'Points For', className: 'text-right' },
                      { key: 'pa', label: 'Points Against', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {records.map((rec, idx) => (
                      <StandardTableRow key={idx}>
                        <td className={tableCell}>{rec.franchise_name_clean || 'Unknown'}</td>
                        <td className={tableCell}>
                          {rec.wins}-{rec.losses}-{rec.ties} ({Number(rec.win_pct || 0).toFixed(3)})
                        </td>
                        <td className={tableCellNumeric}>{Number(rec.points_for || 0).toFixed(1)}</td>
                        <td className={tableCellNumeric}>{Number(rec.points_against || 0).toFixed(1)}</td>
                      </StandardTableRow>
                    ))}
                  </tbody>
                </StandardTable>
              </div>
            )}
          </div>
        )}

        {/* RECORD STREAKS */}
        {normalizedSectionKey === 'record-streaks' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading record streaks..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No streak records found." />
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {records.map((rec, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-bold text-slate-900 dark:text-white">
                          {rec.franchise_name_clean}
                        </p>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          {rec.streak_length}-game {rec.streak_type} Streak
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Week {rec.start_week}, {rec.record_year}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-black text-cyan-600 dark:text-cyan-400">
                          {rec.streak_length}
                        </p>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Games
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Historical-only zone: no current-year operational analytics should appear in this section.
        </p>
      </section>
    </PageTemplate>
  );
}
