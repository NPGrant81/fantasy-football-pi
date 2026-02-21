import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FiChevronLeft,
  FiMail,
  FiTrash2,
  FiSave,
  FiUserPlus,
} from 'react-icons/fi';
import apiClient from '@api/client';

const OWNER_LIMIT_DEFAULT = 12;

export default function ManageOwners() {
  const leagueId = localStorage.getItem('fantasyLeagueId');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [config, setConfig] = useState(null);
  const [ownerLimit, setOwnerLimit] = useState(OWNER_LIMIT_DEFAULT);
  const [owners, setOwners] = useState([]);

  const [newOwnerName, setNewOwnerName] = useState('');
  const [newOwnerEmail, setNewOwnerEmail] = useState('');

  useEffect(() => {
    async function load() {
      if (!leagueId) {
        setError('No active league selected.');
        setLoading(false);
        return;
      }

      try {
        const [settingsRes, ownersRes] = await Promise.all([
          apiClient.get(`/leagues/${leagueId}/settings`),
          apiClient.get(`/leagues/owners?league_id=${leagueId}`),
        ]);

        setConfig(settingsRes.data);
        setOwnerLimit(
          Number(
            settingsRes.data?.starting_slots?.OWNER_LIMIT || OWNER_LIMIT_DEFAULT
          )
        );
        setOwners(
          (ownersRes.data || []).map((owner) => ({ ...owner, _dirty: false }))
        );
      } catch (err) {
        setError(
          err.response?.data?.detail || 'Failed to load owner management data.'
        );
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [leagueId]);

  const ownerCount = owners.length;
  const canAddOwner = ownerCount < Number(ownerLimit || 0);

  const dirtyOwners = useMemo(
    () => owners.filter((owner) => owner._dirty),
    [owners]
  );

  const saveOwnerLimit = async () => {
    if (!config || !leagueId) return;
    setSaving(true);
    setError('');
    setNotice('');

    try {
      const nextStartingSlots = {
        ...(config.starting_slots || {}),
        OWNER_LIMIT: Math.max(2, Number(ownerLimit) || OWNER_LIMIT_DEFAULT),
      };

      const payload = {
        ...config,
        starting_slots: nextStartingSlots,
      };

      await apiClient.put(`/leagues/${leagueId}/settings`, payload);
      setConfig(payload);
      setNotice('Owner limit saved.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save owner limit.');
    } finally {
      setSaving(false);
    }
  };

  const addOwner = async () => {
    if (!newOwnerName || !newOwnerEmail) {
      setError('Name and email are required.');
      return;
    }

    if (!canAddOwner) {
      setError('Owner limit reached. Increase total owners first.');
      return;
    }

    setSaving(true);
    setError('');
    setNotice('');

    try {
      const res = await apiClient.post('/leagues/owners', {
        username: newOwnerName,
        email: newOwnerEmail,
        league_id: Number(leagueId),
      });

      const ownersRes = await apiClient.get(
        `/leagues/owners?league_id=${leagueId}`
      );
      setOwners(
        (ownersRes.data || []).map((owner) => ({ ...owner, _dirty: false }))
      );

      const tempPassword = res.data?.debug_password || '(hidden in production)';
      const assignedLeague = res.data?.league_id ?? leagueId;
      setNotice(
        `Owner invited. League ID: ${assignedLeague}. Temporary password: ${tempPassword}.` +
          ' Email notification was sent (or simulated in console).'
      );

      setNewOwnerName('');
      setNewOwnerEmail('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add owner.');
    } finally {
      setSaving(false);
    }
  };

  const updateOwnerField = (ownerId, field, value) => {
    setOwners((prev) =>
      prev.map((owner) =>
        owner.id === ownerId
          ? { ...owner, [field]: value, _dirty: true }
          : owner
      )
    );
  };

  const saveOwner = async (owner) => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiClient.put(`/leagues/owners/${owner.id}`, {
        username: owner.username,
        email: owner.email,
      });
      setOwners((prev) =>
        prev.map((item) =>
          item.id === owner.id ? { ...item, _dirty: false } : item
        )
      );
      setNotice(`Updated owner ${owner.username}.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update owner.');
    } finally {
      setSaving(false);
    }
  };

  const removeOwner = async (owner) => {
    const confirmed = window.confirm(
      `Remove ${owner.username} from this league? They will be detached from league membership.`
    );
    if (!confirmed) return;

    setSaving(true);
    setError('');
    setNotice('');
    try {
      await apiClient.delete(`/leagues/${leagueId}/members/${owner.id}`);
      setOwners((prev) => prev.filter((item) => item.id !== owner.id));
      setNotice(`${owner.username} removed from league.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove owner.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="text-white text-center mt-20 animate-pulse font-black uppercase tracking-widest">
        Loading Owner Management...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center justify-between mb-8 border-b border-slate-700 pb-5">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Manage Owners
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Set total owners, invite owners, update owner details, and remove
            opt-outs.
          </p>
        </div>
        <Link
          to="/commissioner"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-bold text-slate-300 hover:text-white"
        >
          <FiChevronLeft /> Back
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-800/60 bg-red-900/20 p-3 text-sm text-red-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded-lg border border-green-800/60 bg-green-900/20 p-3 text-sm text-green-200">
          {notice}
        </div>
      )}

      <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
              Total Owners in League
            </label>
            <input
              type="number"
              min={2}
              max={20}
              value={ownerLimit}
              onChange={(e) =>
                setOwnerLimit(Number(e.target.value) || OWNER_LIMIT_DEFAULT)
              }
              className="w-40 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            />
          </div>
          <button
            onClick={saveOwnerLimit}
            disabled={saving}
            className={`rounded-xl px-4 py-2 text-sm font-black uppercase ${saving ? 'bg-slate-800 text-slate-500' : 'bg-purple-600 hover:bg-purple-500 text-white'}`}
          >
            Save Owner Count
          </button>
          <p className="text-xs text-slate-400">Current owners: {ownerCount}</p>
        </div>
      </div>

      <div className="mb-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="mb-4 text-xl font-black uppercase tracking-wider">
          Add New Owner
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={newOwnerName}
            onChange={(e) => setNewOwnerName(e.target.value)}
            placeholder="Owner name"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <input
            value={newOwnerEmail}
            onChange={(e) => setNewOwnerEmail(e.target.value)}
            placeholder="Email address"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <button
            onClick={addOwner}
            disabled={saving || !canAddOwner}
            className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-black uppercase ${saving || !canAddOwner ? 'bg-slate-800 text-slate-500' : 'bg-green-600 hover:bg-green-500 text-white'}`}
          >
            <FiUserPlus /> Send Invite
          </button>
        </div>
        {!canAddOwner && (
          <p className="mt-3 text-xs text-orange-300">
            Owner limit reached. Increase total owners to add more.
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="mb-4 text-xl font-black uppercase tracking-wider">
          Current Owners
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400 uppercase text-xs">
              <tr>
                <th className="pb-3">Name</th>
                <th className="pb-3">Email</th>
                <th className="pb-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {owners.map((owner) => (
                <tr key={owner.id}>
                  <td className="py-3 pr-3">
                    <input
                      value={owner.username || ''}
                      onChange={(e) =>
                        updateOwnerField(owner.id, 'username', e.target.value)
                      }
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
                    />
                  </td>
                  <td className="py-3 pr-3">
                    <input
                      value={owner.email || ''}
                      onChange={(e) =>
                        updateOwnerField(owner.id, 'email', e.target.value)
                      }
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
                    />
                  </td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => saveOwner(owner)}
                        disabled={saving || !owner._dirty}
                        className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${saving || !owner._dirty ? 'bg-slate-800 text-slate-500' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
                      >
                        <FiSave /> Update
                      </button>
                      <button
                        onClick={() => removeOwner(owner)}
                        disabled={saving}
                        className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${saving ? 'bg-slate-800 text-slate-500' : 'bg-red-600 hover:bg-red-500 text-white'}`}
                      >
                        <FiTrash2 /> Remove
                      </button>
                      <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                        <FiMail /> invite/login details sent on add
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {dirtyOwners.length > 0 && (
        <p className="mt-4 text-xs text-orange-300">
          {dirtyOwners.length} owner row(s) have unsaved edits.
        </p>
      )}
    </div>
  );
}
