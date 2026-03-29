import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FiAlertTriangle,
  FiChevronLeft,
  FiClock,
  FiDownload,
  FiEdit2,
  FiFilter,
  FiLayers,
  FiSearch,
  FiSave,
  FiTrash2,
  FiUpload,
  FiUsers,
} from 'react-icons/fi';
import apiClient from '@api/client';
import { useActiveLeague } from '@context/LeagueContext';
import PageTemplate from '@components/layout/PageTemplate';
import { ErrorState, LoadingState } from '@components/common/AsyncState';
import {
  StandardTable,
  StandardTableContainer,
  StandardTableHead,
  StandardTableRow,
} from '@components/table/TablePrimitives';
import {
  buttonDanger,
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  pageShell,
  tableCell,
  textCaption,
  textMeta,
} from '@utils/uiStandards';

const BULK_PLACEHOLDER = [
  '2019|mfl_o_171|Chester Clark|league perspective token',
  '2019|Gridiron Brothers|Alex Grant|legacy team name',
].join('\n');

const CSV_HEADERS = ['season', 'team_name', 'owner_name', 'owner_id', 'notes'];

const CSV_TEMPLATE = [
  CSV_HEADERS.join(','),
  '2019,mfl_o_171,Chester Clark,,league perspective token',
  '2019,Gridiron Brothers,Alex Grant,,legacy team name',
].join('\n');

function normalizeLookup(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeOwnerLabel(owner) {
  return owner.team_name || owner.username || `Owner ${owner.id}`;
}

function parseBulkMappings(rawText) {
  return String(rawText || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const parts = line.split('|').map((part) => part.trim());
      if (parts.length < 3) {
        throw new Error(`Line ${index + 1}: expected season|team|owner|notes`);
      }
      const season = Number(parts[0]);
      if (!Number.isInteger(season) || season < 2000) {
        throw new Error(`Line ${index + 1}: invalid season '${parts[0]}'`);
      }
      if (!parts[1]) {
        throw new Error(`Line ${index + 1}: team/source key is required`);
      }
      return {
        season,
        team_name: parts[1],
        owner_name: parts[2] || null,
        notes: parts[3] || null,
      };
    });
}

function escapeCsvValue(value) {
  const raw = String(value ?? '');
  if (/[",\n]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

function serializeMappingsCsv(rows) {
  const lines = [CSV_HEADERS.join(',')];
  rows.forEach((row) => {
    lines.push(
      [
        row.season,
        row.team_name || '',
        row.owner_name || '',
        row.owner_id || '',
        row.notes || '',
      ]
        .map(escapeCsvValue)
        .join(',')
    );
  });
  return lines.join('\n');
}

function parseCsvLine(line) {
  const cells = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const nextChar = line[index + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      cells.push(current);
      current = '';
      continue;
    }

    current += char;
  }

  cells.push(current);
  return cells.map((cell) => cell.trim());
}

function parseCsvMappings(rawText) {
  const lines = String(rawText || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) {
    throw new Error('CSV import is empty.');
  }

  const parsedLines = lines.map(parseCsvLine);
  const firstRow = parsedLines[0].map((value) => value.toLowerCase());
  const hasHeader = firstRow.includes('season') && firstRow.includes('team_name');

  const indexByField = hasHeader
    ? {
        season: firstRow.indexOf('season'),
        team_name: firstRow.indexOf('team_name'),
        owner_name: firstRow.indexOf('owner_name'),
        owner_id: firstRow.indexOf('owner_id'),
        notes: firstRow.indexOf('notes'),
      }
    : {
        season: 0,
        team_name: 1,
        owner_name: 2,
        owner_id: 3,
        notes: 4,
      };

  const dataRows = hasHeader ? parsedLines.slice(1) : parsedLines;
  return dataRows.map((cells, index) => {
    const sourceLine = index + (hasHeader ? 2 : 1);
    const season = Number(cells[indexByField.season] || '');
    const teamName = String(cells[indexByField.team_name] || '').trim();
    const ownerName = String(cells[indexByField.owner_name] || '').trim();
    const ownerIdRaw = String(cells[indexByField.owner_id] || '').trim();
    const notes = String(cells[indexByField.notes] || '').trim();

    if (!Number.isInteger(season) || season < 2000) {
      throw new Error(`CSV line ${sourceLine}: invalid season.`);
    }
    if (!teamName) {
      throw new Error(`CSV line ${sourceLine}: team_name is required.`);
    }

    return {
      season,
      team_name: teamName,
      owner_name: ownerName || null,
      owner_id: ownerIdRaw ? Number(ownerIdRaw) : null,
      notes: notes || null,
    };
  });
}

function resolveOwnerIds(mappings, owners) {
  const ownerIndexByName = new Map();
  owners.forEach((owner) => {
    [owner.username, owner.team_name].forEach((candidate) => {
      const key = normalizeLookup(candidate);
      if (key && !ownerIndexByName.has(key)) {
        ownerIndexByName.set(key, owner);
      }
    });
  });

  const resolvedMappings = mappings.map((mapping) => {
    const ownerName = String(mapping.owner_name || '').trim() || null;
    let ownerId = mapping.owner_id ? Number(mapping.owner_id) : null;
    const notes = String(mapping.notes || '').trim();

    if (!ownerId && ownerName) {
      const matchedOwner = ownerIndexByName.get(normalizeLookup(ownerName));
      if (matchedOwner) {
        ownerId = Number(matchedOwner.id);
      }
    }

    return {
      ...mapping,
      owner_name: ownerName,
      owner_id: ownerId,
      notes: notes || null,
    };
  });

  return { mappings: resolvedMappings };
}

function downloadTextFile(filename, content, mimeType = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export default function HistoryOwnerMappingUtility() {
  const leagueId = useActiveLeague();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [owners, setOwners] = useState([]);
  const [mappingRows, setMappingRows] = useState([]);
  const [unmappedSeriesKeys, setUnmappedSeriesKeys] = useState([]);
  const [mappedSeriesKeys, setMappedSeriesKeys] = useState([]);

  const [mapEditId, setMapEditId] = useState(null);
  const [seasonInput, setSeasonInput] = useState('');
  const [teamInput, setTeamInput] = useState('');
  const [ownerNameInput, setOwnerNameInput] = useState('');
  const [ownerIdInput, setOwnerIdInput] = useState('');
  const [notesInput, setNotesInput] = useState('');
  const [bulkInput, setBulkInput] = useState('');
  const [seasonFilter, setSeasonFilter] = useState('ALL');
  const [rowTypeFilter, setRowTypeFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [timelineOwnerSearch, setTimelineOwnerSearch] = useState('');
  const [timelineOnlyMultiStint, setTimelineOnlyMultiStint] = useState(false);

  const loadPageData = async () => {
    if (!leagueId) {
      setError('No active league selected.');
      setLoading(false);
      return;
    }

    try {
      const [ownersRes, mappingRes, unmappedRes] = await Promise.all([
        apiClient.get(`/leagues/owners?league_id=${Number(leagueId)}`),
        apiClient.get(`/leagues/${Number(leagueId)}/history/team-owner-map`),
        apiClient.get(`/leagues/${Number(leagueId)}/history/unmapped-series-keys`),
      ]);

      setOwners(Array.isArray(ownersRes.data) ? ownersRes.data : []);
      setMappingRows(Array.isArray(mappingRes?.data?.mappings) ? mappingRes.data.mappings : []);
      setUnmappedSeriesKeys(Array.isArray(unmappedRes?.data?.unmapped) ? unmappedRes.data.unmapped : []);
      setMappedSeriesKeys(Array.isArray(unmappedRes?.data?.mapped) ? unmappedRes.data.mapped : []);
      setError('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load historical mapping utility.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPageData();
  }, [leagueId]);

  const ownerOptions = useMemo(
    () => owners.map((owner) => ({ value: String(owner.id), label: normalizeOwnerLabel(owner) })),
    [owners]
  );

  const seasonOptions = useMemo(() => {
    const values = new Set();
    mappingRows.forEach((row) => {
      if (Number.isInteger(Number(row.season))) {
        values.add(Number(row.season));
      }
    });
    unmappedSeriesKeys.forEach((item) => {
      (item.seasons || []).forEach((season) => {
        if (Number.isInteger(Number(season))) {
          values.add(Number(season));
        }
      });
    });
    return [...values].sort((left, right) => right - left);
  }, [mappingRows, unmappedSeriesKeys]);

  const stats = useMemo(() => {
    const totalUnmapped = unmappedSeriesKeys.length;
    const totalMappedSourceKeys = mappingRows.filter((row) => String(row.team_name || '').toLowerCase().includes('mfl_o_')).length;
    return {
      rowCount: mappingRows.length,
      unmappedCount: totalUnmapped,
      mappedSourceCount: totalMappedSourceKeys,
      coverageCount: totalMappedSourceKeys + totalUnmapped,
    };
  }, [mappingRows, unmappedSeriesKeys]);

  const seasonCoverageRows = useMemo(() => {
    return seasonOptions.map((season) => {
      const mappedRowsForSeason = mappingRows.filter((row) => Number(row.season) === season);
      const mappedSourceCount = mappedRowsForSeason.filter((row) =>
        String(row.team_name || '').toLowerCase().includes('mfl_o_') ||
        String(row.team_name_key || '').toLowerCase().startsWith('mfl o ')
      ).length;
      const manualLabelCount = mappedRowsForSeason.length - mappedSourceCount;
      const unmappedItems = unmappedSeriesKeys.filter((item) =>
        Array.isArray(item.seasons) && item.seasons.some((value) => Number(value) === season)
      );
      const unmappedCount = unmappedItems.length;
      const coverageBase = mappedSourceCount + unmappedCount;
      return {
        season,
        mappedSourceCount,
        manualLabelCount,
        unmappedCount,
        coveragePct: coverageBase > 0 ? Math.round((mappedSourceCount / coverageBase) * 100) : 100,
      };
    });
  }, [mappingRows, seasonOptions, unmappedSeriesKeys]);

  const mappingDiagnostics = useMemo(() => {
    const sourceTokenStats = new Map();
    [...unmappedSeriesKeys, ...mappedSeriesKeys].forEach((item) => {
      const tokenKey = normalizeLookup(item.source_token);
      if (!tokenKey) {
        return;
      }
      sourceTokenStats.set(tokenKey, {
        sourceToken: item.source_token,
        seasons: new Set((item.seasons || []).map((season) => Number(season)).filter((season) => Number.isInteger(season))),
      });
    });

    const ownerIdsInLeague = new Set(owners.map((owner) => Number(owner.id)));
    const missingOwnerRows = [];
    const nameOnlyRows = [];
    const invalidOwnerIdRows = [];
    const sourceTokenMissingRows = [];
    const sourceTokenSeasonMismatchRows = [];

    mappingRows.forEach((row) => {
      const ownerName = String(row.owner_name || '').trim();
      const ownerId = row.owner_id ? Number(row.owner_id) : null;
      const hasOwnerName = Boolean(ownerName);
      const hasOwnerId = ownerId !== null && !Number.isNaN(ownerId);
      const teamNameKey = normalizeLookup(row.team_name_key || row.team_name);
      const season = Number(row.season);
      const isSourceToken = teamNameKey.startsWith('mfl o ');

      if (!hasOwnerName && !hasOwnerId) {
        missingOwnerRows.push(row);
      } else if (hasOwnerName && !hasOwnerId) {
        nameOnlyRows.push(row);
      }

      if (hasOwnerId && !ownerIdsInLeague.has(ownerId)) {
        invalidOwnerIdRows.push(row);
      }

      if (isSourceToken) {
        const sourceToken = sourceTokenStats.get(teamNameKey);
        if (!sourceToken) {
          sourceTokenMissingRows.push(row);
        } else if (sourceToken.seasons.size > 0 && Number.isInteger(season) && !sourceToken.seasons.has(season)) {
          sourceTokenSeasonMismatchRows.push({
            ...row,
            expectedSeasons: [...sourceToken.seasons].sort((left, right) => left - right),
            sourceToken: sourceToken.sourceToken,
          });
        }
      }
    });

    return {
      missingOwnerRows,
      nameOnlyRows,
      invalidOwnerIdRows,
      sourceTokenMissingRows,
      sourceTokenSeasonMismatchRows,
    };
  }, [mappingRows, mappedSeriesKeys, owners, unmappedSeriesKeys]);

  const timelineSeasons = useMemo(() => [...seasonOptions].sort((left, right) => left - right), [seasonOptions]);

  const ownerTimelineRows = useMemo(() => {
    const ownerById = new Map(owners.map((owner) => [Number(owner.id), owner]));
    const ownerGroups = new Map();

    mappingRows.forEach((row) => {
      const ownerId = row.owner_id ? Number(row.owner_id) : null;
      const ownerName = String(row.owner_name || '').trim();
      if (!ownerId && !ownerName) {
        return;
      }

      const ownerKey = ownerId ? `id:${ownerId}` : `name:${normalizeLookup(ownerName)}`;
      if (!ownerGroups.has(ownerKey)) {
        const owner = ownerId ? ownerById.get(ownerId) : null;
        ownerGroups.set(ownerKey, {
          key: ownerKey,
          ownerId,
          ownerLabel: ownerName || (owner ? normalizeOwnerLabel(owner) : 'Unknown Owner'),
          seasons: new Set(),
          teams: new Set(),
        });
      }

      const group = ownerGroups.get(ownerKey);
      const season = Number(row.season);
      if (Number.isInteger(season)) {
        group.seasons.add(season);
      }
      const teamName = String(row.team_name || '').trim();
      if (teamName) {
        group.teams.add(teamName);
      }
    });

    return [...ownerGroups.values()]
      .map((group) => {
        const seasons = [...group.seasons].sort((left, right) => left - right);
        if (seasons.length === 0) {
          return null;
        }

        const segments = [];
        let segmentStart = seasons[0];
        let previous = seasons[0];
        for (let index = 1; index < seasons.length; index += 1) {
          const current = seasons[index];
          if (current === previous + 1) {
            previous = current;
            continue;
          }
          segments.push({ start: segmentStart, end: previous });
          segmentStart = current;
          previous = current;
        }
        segments.push({ start: segmentStart, end: previous });

        return {
          key: group.key,
          ownerId: group.ownerId,
          ownerLabel: group.ownerLabel,
          seasons,
          seasonSet: new Set(seasons),
          teams: [...group.teams],
          teamCount: group.teams.size,
          firstSeason: seasons[0],
          lastSeason: seasons[seasons.length - 1],
          totalSeasons: seasons.length,
          segments,
          multiStint: segments.length > 1,
        };
      })
      .filter(Boolean)
      .sort((left, right) => {
        if (left.firstSeason !== right.firstSeason) {
          return left.firstSeason - right.firstSeason;
        }
        return left.ownerLabel.localeCompare(right.ownerLabel);
      });
  }, [mappingRows, owners]);

  const filteredOwnerTimelineRows = useMemo(() => {
    const query = String(timelineOwnerSearch || '').trim().toLowerCase();
    return ownerTimelineRows.filter((row) => {
      if (timelineOnlyMultiStint && !row.multiStint) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = [
        row.ownerLabel,
        row.ownerId,
        row.firstSeason,
        row.lastSeason,
        row.teams.join(' '),
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [ownerTimelineRows, timelineOnlyMultiStint, timelineOwnerSearch]);

  const filteredMappingRows = useMemo(() => {
    const normalizedSearch = String(searchTerm || '').trim().toLowerCase();
    return mappingRows.filter((row) => {
      if (seasonFilter !== 'ALL' && Number(row.season) !== Number(seasonFilter)) {
        return false;
      }

      const isSourceToken =
        String(row.team_name || '').toLowerCase().includes('mfl_o_') ||
        String(row.team_name_key || '').toLowerCase().startsWith('mfl o ');
      if (rowTypeFilter === 'SOURCE_ONLY' && !isSourceToken) {
        return false;
      }
      if (rowTypeFilter === 'MANUAL_ONLY' && isSourceToken) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const haystack = [
        row.season,
        row.team_name,
        row.team_name_key,
        row.owner_name,
        row.owner_id,
        row.notes,
      ]
        .join(' ')
        .toLowerCase();

      return haystack.includes(normalizedSearch);
    });
  }, [mappingRows, rowTypeFilter, searchTerm, seasonFilter]);

  const resetForm = () => {
    setMapEditId(null);
    setSeasonInput('');
    setTeamInput('');
    setOwnerNameInput('');
    setOwnerIdInput('');
    setNotesInput('');
  };

  const handleOwnerSelect = (value) => {
    setOwnerIdInput(value);
    const selectedOwner = owners.find((owner) => String(owner.id) === String(value));
    if (selectedOwner) {
      setOwnerNameInput(normalizeOwnerLabel(selectedOwner));
    }
  };

  const saveMapping = async () => {
    const seasonValue = Number(seasonInput);
    if (!Number.isInteger(seasonValue) || seasonValue < 2000) {
      setError('Enter a valid season year.');
      return;
    }
    if (!String(teamInput || '').trim()) {
      setError('Team/source key is required.');
      return;
    }

    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiClient.put(`/leagues/${Number(leagueId)}/history/team-owner-map`, {
        mappings: [
          {
            season: seasonValue,
            team_name: String(teamInput || '').trim(),
            owner_name: String(ownerNameInput || '').trim() || null,
            owner_id: ownerIdInput ? Number(ownerIdInput) : null,
            notes: String(notesInput || '').trim() || null,
          },
        ],
      });
      setNotice(mapEditId ? 'Mapping updated.' : 'Mapping saved.');
      resetForm();
      await loadPageData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save mapping.');
    } finally {
      setSaving(false);
    }
  };

  const deleteMapping = async (id) => {
    setError('');
    setNotice('');
    try {
      await apiClient.delete(`/leagues/${Number(leagueId)}/history/team-owner-map/${id}`);
      if (mapEditId === id) {
        resetForm();
      }
      setNotice('Mapping deleted.');
      await loadPageData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete mapping.');
    }
  };

  const importBulkMappings = async () => {
    let mappings;
    try {
      mappings = parseBulkMappings(bulkInput);
    } catch (err) {
      setError(err.message || 'Bulk import failed.');
      return;
    }

    const normalizedImport = resolveOwnerIds(mappings, owners);

    setBulkSaving(true);
    setError('');
    setNotice('');
    try {
      await apiClient.put(`/leagues/${Number(leagueId)}/history/team-owner-map`, {
        mappings: normalizedImport.mappings,
      });
      setNotice(`Imported ${normalizedImport.mappings.length} mapping rows.`);
      setBulkInput('');
      await loadPageData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Bulk import failed.');
    } finally {
      setBulkSaving(false);
    }
  };

  const importCsvMappings = async (rawText) => {
    let mappings;
    try {
      mappings = parseCsvMappings(rawText);
    } catch (err) {
      setError(err.message || 'CSV import failed.');
      return;
    }

    const normalizedImport = resolveOwnerIds(mappings, owners);

    setBulkSaving(true);
    setError('');
    setNotice('');
    try {
      await apiClient.put(`/leagues/${Number(leagueId)}/history/team-owner-map`, {
        mappings: normalizedImport.mappings,
      });
      setNotice(`Imported ${normalizedImport.mappings.length} CSV mapping rows.`);
      await loadPageData();
    } catch (err) {
      setError(err.response?.data?.detail || 'CSV import failed.');
    } finally {
      setBulkSaving(false);
    }
  };

  const handleCsvUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    const text = await file.text();
    await importCsvMappings(text);
  };

  const downloadCsvTemplate = () => {
    downloadTextFile('history-owner-mapping-template.csv', CSV_TEMPLATE, 'text/csv;charset=utf-8');
  };

  const exportCurrentMappingsCsv = () => {
    downloadTextFile(
      `league-${Number(leagueId)}-history-owner-mappings.csv`,
      serializeMappingsCsv(mappingRows),
      'text/csv;charset=utf-8'
    );
  };

  if (loading) {
    return (
      <div className={pageShell}>
        <LoadingState message="Loading historical owner mapping utility..." className="mt-20" />
      </div>
    );
  }

  if (error && !mappingRows.length && !owners.length && !unmappedSeriesKeys.length) {
    return (
      <div className={pageShell}>
        <ErrorState message={error} className="mt-20" />
      </div>
    );
  }

  return (
    <PageTemplate
      title="Historical Owner Mapping"
      subtitle="Commissioner utility for resolving historical team names and source tokens by season"
      metadata={
        <span className="inline-flex items-center gap-2">
          <FiClock className="text-cyan-500" />
          Temporary workflow, persistent data
        </span>
      }
    >
      <div className="mb-4 flex items-center gap-3">
        <Link to="/commissioner" className={buttonSecondary}>
          <FiChevronLeft />
          Back to Commissioner
        </Link>
        <span className={textMeta}>When mapping coverage is complete, this page can be hidden without removing the stored mappings.</span>
      </div>

      {(error || notice) && (
        <div className={`${cardSurface} mb-4 p-3`}>
          {error ? <p className="text-sm text-rose-500">{error}</p> : null}
          {notice ? <p className="text-sm text-emerald-600 dark:text-emerald-400">{notice}</p> : null}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className={`${cardSurface} p-4`}>
          <p className={textCaption}>Stored Rows</p>
          <p className="mt-2 text-3xl font-black text-slate-900 dark:text-white">{stats.rowCount}</p>
        </div>
        <div className={`${cardSurface} p-4`}>
          <p className={textCaption}>Unmapped Tokens</p>
          <p className="mt-2 text-3xl font-black text-amber-600 dark:text-amber-400">{stats.unmappedCount}</p>
        </div>
        <div className={`${cardSurface} p-4`}>
          <p className={textCaption}>Mapped Source Keys</p>
          <p className="mt-2 text-3xl font-black text-cyan-600 dark:text-cyan-400">{stats.mappedSourceCount}</p>
        </div>
        <div className={`${cardSurface} p-4`}>
          <p className={textCaption}>Coverage</p>
          <p className="mt-2 text-3xl font-black text-slate-900 dark:text-white">
            {stats.coverageCount > 0 ? `${Math.round((stats.mappedSourceCount / stats.coverageCount) * 100)}%` : '0%'}
          </p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section className={`${cardSurface} p-5`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Manual Mapping</h2>
              <p className={`${textMeta} mt-1`}>Assign an owner name and optional current owner ID to a historical team label or source token for a season.</p>
            </div>
            {mapEditId ? (
              <button type="button" className={buttonSecondary} onClick={resetForm}>
                Cancel Edit
              </button>
            ) : null}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <input
              value={seasonInput}
              onChange={(event) => setSeasonInput(event.target.value)}
              placeholder="Season (e.g. 2019)"
              className={inputBase}
            />
            <input
              value={teamInput}
              onChange={(event) => setTeamInput(event.target.value)}
              placeholder="Historical team name or source key"
              className={inputBase}
            />
            <select
              value={ownerIdInput}
              onChange={(event) => handleOwnerSelect(event.target.value)}
              className={inputBase}
            >
              <option value="">No current owner linked</option>
              {ownerOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              value={ownerNameInput}
              onChange={(event) => setOwnerNameInput(event.target.value)}
              placeholder="Owner display name"
              className={inputBase}
            />
          </div>
          <div className="mt-3 flex gap-3">
            <input
              value={notesInput}
              onChange={(event) => setNotesInput(event.target.value)}
              placeholder="Notes (optional)"
              className={inputBase}
            />
            <button type="button" className={buttonPrimary} disabled={saving} onClick={saveMapping}>
              <FiSave />
              {saving ? 'Saving...' : mapEditId ? 'Update Mapping' : 'Save Mapping'}
            </button>
          </div>

          <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/60">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-200">
              <FiLayers />
              Unmapped Source Tokens
            </div>
            <p className={`${textMeta} mt-1`}>
              Click a token to seed the form. Tokens disappear from this list once a matching mapping key exists.
            </p>
            {unmappedSeriesKeys.length === 0 ? (
              <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-300">No unmapped series tokens remain for this league.</p>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {unmappedSeriesKeys.map((item) => (
                  <button
                    key={item.source_token}
                    type="button"
                    className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-100 dark:hover:bg-amber-800"
                    onClick={() => {
                      setTeamInput(item.source_token.replace(/ /g, '_'));
                      if (!seasonInput && Array.isArray(item.seasons) && item.seasons.length > 0) {
                        setSeasonInput(String(item.seasons[0]));
                      }
                    }}
                  >
                    {item.source_token} · {item.season_count} seasons
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className={`${cardSurface} p-5`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Bulk Import / Export</h2>
              <p className={`${textMeta} mt-1`}>Use CSV for repeatable data work and pipe-delimited paste for quick cleanup. Existing keys are updated in place.</p>
            </div>
            <div className="inline-flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              <FiDownload />
              CSV + pipe import
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className={buttonSecondary} onClick={downloadCsvTemplate}>
              <FiDownload />
              Download CSV Template
            </button>
            <button type="button" className={buttonSecondary} onClick={exportCurrentMappingsCsv}>
              <FiDownload />
              Export Current Mappings
            </button>
            <label className={`${buttonPrimary} cursor-pointer`}>
              <FiUpload />
              Upload CSV
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={handleCsvUpload}
              />
            </label>
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900/60">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">CSV Columns</p>
            <p className={`${textMeta} mt-1`}>
              Required: `season`, `team_name`. Optional: `owner_name`, `owner_id`, `notes`.
            </p>
            <p className={`${textMeta} mt-1`}>
              Owner names are preserved exactly as imported; IDs are auto-resolved only when the owner name matches an active league owner.
            </p>
          </div>

          <textarea
            value={bulkInput}
            onChange={(event) => setBulkInput(event.target.value)}
            rows={14}
            placeholder={BULK_PLACEHOLDER}
            className={`${inputBase} mt-4 min-h-[18rem] font-mono text-xs`}
          />

          <div className="mt-3 flex items-center justify-between gap-3">
            <p className={textMeta}>Use current owner IDs only when the historical owner maps cleanly to an existing owner account. Pipe format stays `season|team|owner|notes`.</p>
            <button type="button" className={buttonPrimary} disabled={bulkSaving} onClick={importBulkMappings}>
              <FiUpload />
              {bulkSaving ? 'Importing...' : 'Import Pipe Rows'}
            </button>
          </div>
        </section>
      </div>

      <section className={`${cardSurface} mt-6 p-5`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Season Coverage</h2>
            <p className={`${textMeta} mt-1`}>Use this to work season-by-season and see where source-token coverage is still incomplete.</p>
          </div>
          <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <FiLayers />
            {seasonCoverageRows.length} seasons tracked
          </div>
        </div>

        {seasonCoverageRows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            No seasonal coverage data yet.
          </div>
        ) : (
          <StandardTableContainer className="mt-4">
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'season', label: 'Season' },
                  { key: 'mapped', label: 'Mapped Source Keys' },
                  { key: 'manual', label: 'Manual Team Rows' },
                  { key: 'unmapped', label: 'Unmapped Source Keys' },
                  { key: 'coverage', label: 'Coverage' },
                ]}
              />
              <tbody>
                {seasonCoverageRows.map((row) => (
                  <StandardTableRow key={row.season}>
                    <td className={tableCell}>{row.season}</td>
                    <td className={tableCell}>{row.mappedSourceCount}</td>
                    <td className={tableCell}>{row.manualLabelCount}</td>
                    <td className={tableCell}>{row.unmappedCount}</td>
                    <td className={tableCell}>
                      <div className="flex items-center gap-3">
                        <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                          <div
                            className={`h-full rounded-full ${row.coveragePct >= 100 ? 'bg-emerald-500' : row.coveragePct >= 70 ? 'bg-cyan-500' : 'bg-amber-500'}`}
                            style={{ width: `${Math.max(6, row.coveragePct)}%` }}
                          />
                        </div>
                        <button
                          type="button"
                          className="font-semibold text-cyan-600 hover:underline dark:text-cyan-300"
                          onClick={() => setSeasonFilter(String(row.season))}
                        >
                          {row.coveragePct}%
                        </button>
                      </div>
                    </td>
                  </StandardTableRow>
                ))}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
      </section>

      <section className={`${cardSurface} mt-6 p-5`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Mapping Diagnostics</h2>
            <p className={`${textMeta} mt-1`}>
              Use this to spot exactly why rows are not appearing as mapped in owner views.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <FiAlertTriangle />
            {mappingDiagnostics.missingOwnerRows.length + mappingDiagnostics.sourceTokenMissingRows.length + mappingDiagnostics.sourceTokenSeasonMismatchRows.length} blocking flags
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/70 dark:bg-rose-950/30">
            <p className={textCaption}>No owner name or ID</p>
            <p className="mt-1 text-2xl font-black text-rose-700 dark:text-rose-300">{mappingDiagnostics.missingOwnerRows.length}</p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/70 dark:bg-amber-950/30">
            <p className={textCaption}>Name only, no owner ID</p>
            <p className="mt-1 text-2xl font-black text-amber-700 dark:text-amber-300">{mappingDiagnostics.nameOnlyRows.length}</p>
          </div>
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/70 dark:bg-rose-950/30">
            <p className={textCaption}>Owner ID not in league</p>
            <p className="mt-1 text-2xl font-black text-rose-700 dark:text-rose-300">{mappingDiagnostics.invalidOwnerIdRows.length}</p>
          </div>
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 dark:border-rose-900/70 dark:bg-rose-950/30">
            <p className={textCaption}>Source token not found</p>
            <p className="mt-1 text-2xl font-black text-rose-700 dark:text-rose-300">{mappingDiagnostics.sourceTokenMissingRows.length}</p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/70 dark:bg-amber-950/30">
            <p className={textCaption}>Source token season mismatch</p>
            <p className="mt-1 text-2xl font-black text-amber-700 dark:text-amber-300">{mappingDiagnostics.sourceTokenSeasonMismatchRows.length}</p>
          </div>
        </div>

        {(mappingDiagnostics.missingOwnerRows.length > 0 ||
          mappingDiagnostics.sourceTokenMissingRows.length > 0 ||
          mappingDiagnostics.sourceTokenSeasonMismatchRows.length > 0 ||
          mappingDiagnostics.nameOnlyRows.length > 0 ||
          mappingDiagnostics.invalidOwnerIdRows.length > 0) ? (
          <div className="mt-4 space-y-3">
            {mappingDiagnostics.missingOwnerRows.slice(0, 8).map((row) => (
              <div key={`missing-owner-${row.id}`} className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm dark:border-rose-900/60 dark:bg-rose-950/30">
                <span className="font-semibold text-rose-800 dark:text-rose-200">No owner fields:</span>{' '}
                {row.season} / {row.team_name}
              </div>
            ))}
            {mappingDiagnostics.nameOnlyRows.slice(0, 6).map((row) => (
              <div key={`name-only-${row.id}`} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm dark:border-amber-900/60 dark:bg-amber-950/30">
                <span className="font-semibold text-amber-800 dark:text-amber-200">Name-only mapping:</span>{' '}
                {row.season} / {row.team_name} {'->'} {row.owner_name}
              </div>
            ))}
            {mappingDiagnostics.invalidOwnerIdRows.slice(0, 6).map((row) => (
              <div key={`owner-id-invalid-${row.id}`} className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm dark:border-rose-900/60 dark:bg-rose-950/30">
                <span className="font-semibold text-rose-800 dark:text-rose-200">Owner ID missing from current league:</span>{' '}
                {row.season} / {row.team_name} {'->'} ID {row.owner_id}
              </div>
            ))}
            {mappingDiagnostics.sourceTokenMissingRows.slice(0, 8).map((row) => (
              <div key={`token-missing-${row.id}`} className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm dark:border-rose-900/60 dark:bg-rose-950/30">
                <span className="font-semibold text-rose-800 dark:text-rose-200">Source token not in historical feed:</span>{' '}
                {row.season} / {row.team_name}
              </div>
            ))}
            {mappingDiagnostics.sourceTokenSeasonMismatchRows.slice(0, 8).map((row) => (
              <div key={`token-season-${row.id}`} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm dark:border-amber-900/60 dark:bg-amber-950/30">
                <span className="font-semibold text-amber-800 dark:text-amber-200">Season mismatch for source token:</span>{' '}
                {row.season} / {row.team_name} (valid seasons: {row.expectedSeasons.join(', ')})
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200">
            No mapping issues detected from currently loaded historical source tokens.
          </div>
        )}
      </section>

      <section className={`${cardSurface} mt-6 p-5`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Owner Timeline</h2>
            <p className={`${textMeta} mt-1`}>
              Visual timeline of owner tenure by season. Each highlighted block marks a season with at least one mapped historical team row.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <FiUsers />
            {filteredOwnerTimelineRows.length} owners shown
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
          <label className="relative">
            <FiSearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={timelineOwnerSearch}
              onChange={(event) => setTimelineOwnerSearch(event.target.value)}
              placeholder="Filter owner timeline by owner, ID, season, or team"
              className={`${inputBase} pl-10`}
            />
          </label>
          <label className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              checked={timelineOnlyMultiStint}
              onChange={(event) => setTimelineOnlyMultiStint(event.target.checked)}
            />
            Multi-stint owners only
          </label>
        </div>

        {!timelineSeasons.length || !filteredOwnerTimelineRows.length ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            No owner timeline data matches the current filters.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <div className="min-w-[52rem]">
              <div className="mb-2 grid grid-cols-[18rem_1fr] items-end gap-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Owner</div>
                <div
                  className="grid gap-1"
                  style={{ gridTemplateColumns: `repeat(${timelineSeasons.length}, minmax(0, 1fr))` }}
                >
                  {timelineSeasons.map((season) => (
                    <div key={`header-${season}`} className="text-center text-[10px] font-semibold text-slate-500 dark:text-slate-400">
                      {season}
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                {filteredOwnerTimelineRows.map((row) => (
                  <div key={row.key} className="grid grid-cols-[18rem_1fr] items-center gap-3">
                    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900/60">
                      <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{row.ownerLabel}</p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {row.firstSeason}-{row.lastSeason} · {row.totalSeasons} seasons · {row.teamCount} teams
                        {row.ownerId ? ` · ID ${row.ownerId}` : ''}
                      </p>
                      {row.multiStint ? (
                        <p className="mt-1 text-[11px] font-semibold text-amber-700 dark:text-amber-300">
                          {row.segments.length} stints: {row.segments.map((segment) => `${segment.start}-${segment.end}`).join(', ')}
                        </p>
                      ) : null}
                    </div>

                    <div
                      className="grid gap-1"
                      style={{ gridTemplateColumns: `repeat(${timelineSeasons.length}, minmax(0, 1fr))` }}
                    >
                      {timelineSeasons.map((season, index) => {
                        const isActive = row.seasonSet.has(season);
                        const prevActive = index > 0 ? row.seasonSet.has(timelineSeasons[index - 1]) : false;
                        const nextActive = index < timelineSeasons.length - 1 ? row.seasonSet.has(timelineSeasons[index + 1]) : false;
                        const roundedLeft = isActive && !prevActive;
                        const roundedRight = isActive && !nextActive;

                        return (
                          <div
                            key={`${row.key}-${season}`}
                            title={`${row.ownerLabel} · ${season}`}
                            className={`h-7 border border-slate-200 dark:border-slate-700 ${
                              isActive
                                ? `bg-cyan-500/80 dark:bg-cyan-400/70 ${roundedLeft ? 'rounded-l-md' : ''} ${roundedRight ? 'rounded-r-md' : ''}`
                                : 'bg-slate-100 dark:bg-slate-900/50'
                            }`}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      <section className={`${cardSurface} mt-6 p-5`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900 dark:text-white">Stored Mapping Rows</h2>
            <p className={`${textMeta} mt-1`}>Edit rows in place as coverage improves. Source-token rows are highlighted by the `mfl_o_` prefix.</p>
          </div>
          <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <FiUsers />
            {filteredMappingRows.length} shown
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto_auto]">
          <label className="relative">
            <FiSearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search by team, source key, owner, notes, or owner ID"
              className={`${inputBase} pl-10`}
            />
          </label>
          <label className="flex items-center gap-2">
            <FiFilter className="text-slate-400" />
            <select
              value={seasonFilter}
              onChange={(event) => setSeasonFilter(event.target.value)}
              className={inputBase}
            >
              <option value="ALL">All seasons</option>
              {seasonOptions.map((season) => (
                <option key={season} value={season}>
                  {season}
                </option>
              ))}
            </select>
          </label>
          <select
            value={rowTypeFilter}
            onChange={(event) => setRowTypeFilter(event.target.value)}
            className={inputBase}
          >
            <option value="ALL">All row types</option>
            <option value="SOURCE_ONLY">Source token rows</option>
            <option value="MANUAL_ONLY">Manual team-name rows</option>
          </select>
        </div>

        {filteredMappingRows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            No mapping rows match the current filters.
          </div>
        ) : (
          <StandardTableContainer className="mt-4 max-h-[32rem] overflow-y-auto">
            <StandardTable>
              <StandardTableHead
                headers={[
                  { key: 'season', label: 'Season' },
                  { key: 'team', label: 'Team / Source Key' },
                  { key: 'owner', label: 'Owner' },
                  { key: 'notes', label: 'Notes' },
                  { key: 'actions', label: 'Actions' },
                ]}
              />
              <tbody>
                {filteredMappingRows.map((row) => {
                  const isSourceToken = String(row.team_name || '').toLowerCase().includes('mfl_o_');
                  return (
                    <StandardTableRow key={row.id} className={isSourceToken ? 'bg-amber-50/70 dark:bg-amber-950/20' : ''}>
                      <td className={tableCell}>{row.season}</td>
                      <td className={tableCell}>
                        <div className="font-semibold text-slate-900 dark:text-white">{row.team_name}</div>
                        <div className={textMeta}>{row.team_name_key}</div>
                      </td>
                      <td className={tableCell}>{row.owner_name || 'Unassigned'}</td>
                      <td className={tableCell}>{row.notes || '—'}</td>
                      <td className={tableCell}>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className={buttonSecondary}
                            onClick={() => {
                              setMapEditId(row.id);
                              setSeasonInput(String(row.season));
                              setTeamInput(row.team_name || '');
                              setOwnerNameInput(row.owner_name || '');
                              setOwnerIdInput(row.owner_id ? String(row.owner_id) : '');
                              setNotesInput(row.notes || '');
                              setError('');
                              setNotice('');
                            }}
                          >
                            <FiEdit2 />
                            Edit
                          </button>
                          <button
                            type="button"
                            className={buttonDanger}
                            onClick={() => deleteMapping(row.id)}
                          >
                            <FiTrash2 />
                            Delete
                          </button>
                        </div>
                      </td>
                    </StandardTableRow>
                  );
                })}
              </tbody>
            </StandardTable>
          </StandardTableContainer>
        )}
      </section>
    </PageTemplate>
  );
}