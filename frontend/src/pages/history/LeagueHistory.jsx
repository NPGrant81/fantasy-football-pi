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
import { FiAward, FiTrendingUp, FiUsers, FiBarChart3 } from 'react-icons/fi';

const HISTORY_SECTIONS = [
  { key: 'historical-analytics', label: 'Historical Analytics' },
  { key: 'champions', label: 'League Champions' },
  { key: 'awards', label: 'Awards' },
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
    title: 'League Champions',
    detail: 'All league champions throughout league history.',
  },
  awards: {
    title: 'Awards',
    detail: 'Historical awards and seasonal honors.',
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
  
  // Draft archive specific
  const [archiveSeasonOptions, setArchiveSeasonOptions] = useState([]);
  const [archiveYear, setArchiveYear] = useState('');
  const [archiveHistory, setArchiveHistory] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState('');
  
  // Historical records
  const [records, setRecords] = useState([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsError, setRecordsError] = useState('');
  const [owners, setOwners] = useState([]);

  const ownerNameById = useMemo(() => {
    const index = {};
    owners.forEach((owner) => {
      index[Number(owner.id)] = owner.team_name || owner.username || `Owner ${owner.id}`;
    });
    return index;
  }, [owners]);

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
  useEffect(() => {
    if (!leagueId || !archiveYear || sectionKey !== 'historical-analytics') {
      return;
    }
    
    apiClient
      .get(`/draft/history/by-year?league_id=${Number(leagueId)}&year=${Number(archiveYear)}`)
      .then((response) => {
        setArchiveHistory(Array.isArray(response.data) ? response.data : []);
        setArchiveError('');
        setArchiveLoading(false);
      })
      .catch(() => {
        setArchiveHistory([]);
        setArchiveError('Unable to load archive results for that season.');
        setArchiveLoading(false);
      });
  }, [leagueId, archiveYear, sectionKey]);

  // Load historical records based on section key
  useEffect(() => {
    if (!leagueId || sectionKey === 'historical-analytics' || sectionKey === 'season-records') {
      return;
    }

    const endpointMap = {
      champions: 'champions',
      awards: 'awards',
      'franchise-records': 'records/franchise',
      'player-records': 'records/player',
      'match-records': 'records/match',
      'all-time-series-records': 'records/all-time-series',
      'career-records': 'records/career',
      'record-streaks': 'records/streaks',
    };

    const endpoint = endpointMap[sectionKey];
    if (!endpoint) {
      return;
    }

    apiClient
      .get(`/leagues/${Number(leagueId)}/history/${endpoint}`)
      .then((response) => {
        setRecords(response.data?.records || []);
        setRecordsError('');
        setRecordsLoading(false);
      })
      .catch(() => {
        setRecords([]);
        setRecordsError(`Unable to load ${SECTION_TEXT[sectionKey].title.toLowerCase()}.`);
        setRecordsLoading(false);
      });
  }, [leagueId, sectionKey]);

  const active = SECTION_TEXT[sectionKey] || SECTION_TEXT['historical-analytics'];

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
              section.key === sectionKey
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
        {sectionKey === 'historical-analytics' && (
          <div className="mt-4 rounded-lg border border-slate-300 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-800 dark:text-slate-200">
                <FiBarChart3 className="inline mr-2" />
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
                    {[...archiveHistory]
                      .sort(
                        (a, b) =>
                          new Date(a.timestamp || 0).getTime() -
                          new Date(b.timestamp || 0).getTime()
                      )
                      .map((pick) => (
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
          </div>
        )}

        {/* SEASON RECORDS - Playoff Brackets */}
        {sectionKey === 'season-records' && (
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
        {sectionKey === 'champions' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading league champions..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No champion records found." />
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {records.map((rec, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-bold text-slate-900 dark:text-white">
                          {rec.champion_season || rec.season}
                        </p>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          {rec.franchise_name_clean || 'Unknown'} {rec.place_rank && `(${Number(rec.place_rank) === 1 ? '🏆 Champion' : `Place ${rec.place_rank}`})`}
                        </p>
                      </div>
                      <FiAward className="text-amber-500 text-xl" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* AWARDS */}
        {sectionKey === 'awards' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading awards..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No award records found." />
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {records.map((rec, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-300 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-bold text-slate-900 dark:text-white">
                          {rec.award_title || 'Award'}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {rec.award_season}
                        </p>
                        <p className="text-sm text-slate-700 dark:text-slate-300">
                          {rec.franchise_name_clean || 'Unknown'}
                        </p>
                      </div>
                      <FiAward className="text-amber-500 text-lg flex-shrink-0" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* FRANCHISE RECORDS */}
        {sectionKey === 'franchise-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading franchise records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No franchise records found." />
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'franchise', label: 'Franchise' },
                      { key: 'year', label: 'Year' },
                      { key: 'points', label: 'Points', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {records.map((rec, idx) => (
                      <StandardTableRow key={idx}>
                        <td className={tableCell}>{rec.franchise_name_clean || 'Unknown'}</td>
                        <td className={tableCell}>{rec.record_year} (Week {rec.record_week})</td>
                        <td className={tableCellNumeric}>{Number(rec.points || 0).toFixed(2)}</td>
                      </StandardTableRow>
                    ))}
                  </tbody>
                </StandardTable>
              </div>
            )}
          </div>
        )}

        {/* PLAYER RECORDS */}
        {sectionKey === 'player-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading player records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No player records found." />
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'player', label: 'Player' },
                      { key: 'owner', label: 'Owner' },
                      { key: 'week', label: 'Week / Year' },
                      { key: 'points', label: 'Points', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {records.map((rec, idx) => (
                      <StandardTableRow key={idx}>
                        <td className={tableCell}>{rec.player_name || 'Unknown'} ({rec.position})</td>
                        <td className={tableCell}>{rec.owner_context_raw || '-'}</td>
                        <td className={tableCell}>Week {rec.record_week}, {rec.record_year}</td>
                        <td className={tableCellNumeric}>{Number(rec.points || 0).toFixed(2)}</td>
                      </StandardTableRow>
                    ))}
                  </tbody>
                </StandardTable>
              </div>
            )}
          </div>
        )}

        {/* MATCH RECORDS */}
        {sectionKey === 'match-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading matchup records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No matchup records found." />
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'matchup', label: 'Matchup' },
                      { key: 'score', label: 'Score', className: 'text-right' },
                      { key: 'combined', label: 'Combined Total', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {records.map((rec, idx) => (
                      <StandardTableRow key={idx}>
                        <td className={tableCell}>
                          <div>
                            <p className="font-semibold">{rec.away_franchise_raw} @ {rec.home_franchise_raw}</p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">Week {rec.record_week}, {rec.record_year}</p>
                          </div>
                        </td>
                        <td className={tableCellNumeric}>
                          <div>
                            <p>{Number(rec.away_points || 0).toFixed(2)}</p>
                            <p>{Number(rec.home_points || 0).toFixed(2)}</p>
                          </div>
                        </td>
                        <td className={tableCellNumeric}>{Number(rec.combined_score || 0).toFixed(2)}</td>
                      </StandardTableRow>
                    ))}
                  </tbody>
                </StandardTable>
              </div>
            )}
          </div>
        )}

        {/* ALL-TIME SERIES RECORDS */}
        {sectionKey === 'all-time-series-records' && (
          <div className="mt-4">
            {recordsLoading ? (
              <LoadingState message="Loading all-time series records..." />
            ) : recordsError ? (
              <EmptyState message={recordsError} />
            ) : records.length === 0 ? (
              <EmptyState message="No series records found." />
            ) : (
              <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-300 dark:border-slate-700">
                <StandardTable>
                  <StandardTableHead
                    headers={[
                      { key: 'opponent', label: 'Opponent' },
                      { key: 'season', label: 'Season Record' },
                      { key: 'total', label: 'All-Time Record' },
                      { key: 'pct', label: 'Win %', className: 'text-right' },
                    ]}
                  />
                  <tbody>
                    {records.map((rec, idx) => (
                      <StandardTableRow key={idx}>
                        <td className={tableCell}>{rec.opponent_franchise_raw || 'Unknown'}</td>
                        <td className={tableCell}>{rec.season_w_l_t_raw || '-'}</td>
                        <td className={tableCell}>{rec.total_w_l_t_raw || '-'}</td>
                        <td className={tableCellNumeric}>{Number(rec.total_pct || 0).toFixed(1)}%</td>
                      </StandardTableRow>
                    ))}
                  </tbody>
                </StandardTable>
              </div>
            )}
          </div>
        )}

        {/* CAREER RECORDS */}
        {sectionKey === 'career-records' && (
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
        {sectionKey === 'record-streaks' && (
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
