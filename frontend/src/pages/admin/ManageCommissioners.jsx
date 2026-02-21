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

export default function ManageCommissioners() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [commissioners, setCommissioners] = useState([]);

  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newLeagueId, setNewLeagueId] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const res = await apiClient.get('/admin/tools/commissioners');
        setCommissioners(
          (res.data || []).map((item) => ({ ...item, _dirty: false }))
        );
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load commissioners.');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const dirtyRows = useMemo(
    () => commissioners.filter((commissioner) => commissioner._dirty),
    [commissioners]
  );

  const addCommissioner = async () => {
    if (!newName || !newEmail) {
      setError('Name and email are required.');
      return;
    }

    setSaving(true);
    setError('');
    setNotice('');

    try {
      const payload = {
        username: newName,
        email: newEmail,
        league_id: newLeagueId ? Number(newLeagueId) : null,
      };
      const res = await apiClient.post('/admin/tools/commissioners', payload);
      const refresh = await apiClient.get('/admin/tools/commissioners');
      setCommissioners(
        (refresh.data || []).map((item) => ({ ...item, _dirty: false }))
      );

      const tempPassword = res.data?.debug_password || '(hidden in production)';
      const leagueValue = res.data?.league_id ?? '(not assigned)';
      setNotice(
        `Commissioner invited. League ID: ${leagueValue}. Temporary password: ${tempPassword}.` +
          ' Email notification was sent (or simulated in console).'
      );

      setNewName('');
      setNewEmail('');
      setNewLeagueId('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add commissioner.');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (commissionerId, field, value) => {
    setCommissioners((prev) =>
      prev.map((item) =>
        item.id === commissionerId
          ? { ...item, [field]: value, _dirty: true }
          : item
      )
    );
  };

  const saveCommissioner = async (commissioner) => {
    setSaving(true);
    setError('');
    setNotice('');

    try {
      await apiClient.put(`/admin/tools/commissioners/${commissioner.id}`, {
        username: commissioner.username,
        email: commissioner.email,
        league_id: commissioner.league_id
          ? Number(commissioner.league_id)
          : null,
      });
      setCommissioners((prev) =>
        prev.map((item) =>
          item.id === commissioner.id ? { ...item, _dirty: false } : item
        )
      );
      setNotice(`Updated commissioner ${commissioner.username}.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update commissioner.');
    } finally {
      setSaving(false);
    }
  };

  const removeCommissioner = async (commissioner) => {
    const confirmed = window.confirm(
      `Remove commissioner access for ${commissioner.username}?`
    );
    if (!confirmed) return;

    setSaving(true);
    setError('');
    setNotice('');

    try {
      await apiClient.delete(`/admin/tools/commissioners/${commissioner.id}`);
      setCommissioners((prev) =>
        prev.filter((item) => item.id !== commissioner.id)
      );
      setNotice(`Commissioner access removed for ${commissioner.username}.`);
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Failed to remove commissioner access.'
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="text-white text-center mt-20 animate-pulse font-black uppercase tracking-widest">
        Loading Commissioner Management...
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto text-white min-h-screen">
      <div className="flex items-center justify-between mb-8 border-b border-slate-700 pb-5">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Invite / Manage Commissioners
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Invite commissioners, update account details, assign league IDs, and
            remove commissioner access.
          </p>
        </div>
        <Link
          to="/admin"
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
        <h2 className="mb-4 text-xl font-black uppercase tracking-wider">
          Invite New Commissioner
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Commissioner name"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <input
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="Email address"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <input
            value={newLeagueId}
            onChange={(e) => setNewLeagueId(e.target.value)}
            placeholder="League ID (optional)"
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          />
          <button
            onClick={addCommissioner}
            disabled={saving}
            className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-black uppercase ${saving ? 'bg-slate-800 text-slate-500' : 'bg-green-600 hover:bg-green-500 text-white'}`}
          >
            <FiUserPlus /> Send Invite
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="mb-4 text-xl font-black uppercase tracking-wider">
          Current Commissioners
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400 uppercase text-xs">
              <tr>
                <th className="pb-3">Name</th>
                <th className="pb-3">Email</th>
                <th className="pb-3">League ID</th>
                <th className="pb-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {commissioners.map((commissioner) => (
                <tr key={commissioner.id}>
                  <td className="py-3 pr-3">
                    <input
                      value={commissioner.username || ''}
                      onChange={(e) =>
                        updateField(commissioner.id, 'username', e.target.value)
                      }
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
                    />
                  </td>
                  <td className="py-3 pr-3">
                    <input
                      value={commissioner.email || ''}
                      onChange={(e) =>
                        updateField(commissioner.id, 'email', e.target.value)
                      }
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
                    />
                  </td>
                  <td className="py-3 pr-3">
                    <input
                      value={commissioner.league_id ?? ''}
                      onChange={(e) =>
                        updateField(
                          commissioner.id,
                          'league_id',
                          e.target.value
                        )
                      }
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-white"
                    />
                  </td>
                  <td className="py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => saveCommissioner(commissioner)}
                        disabled={saving || !commissioner._dirty}
                        className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${saving || !commissioner._dirty ? 'bg-slate-800 text-slate-500' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
                      >
                        <FiSave /> Update
                      </button>
                      <button
                        onClick={() => removeCommissioner(commissioner)}
                        disabled={saving || commissioner.is_superuser}
                        className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-bold ${saving || commissioner.is_superuser ? 'bg-slate-800 text-slate-500' : 'bg-red-600 hover:bg-red-500 text-white'}`}
                      >
                        <FiTrash2 /> Remove Access
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

      {dirtyRows.length > 0 && (
        <p className="mt-4 text-xs text-orange-300">
          {dirtyRows.length} commissioner row(s) have unsaved edits.
        </p>
      )}
    </div>
  );
}
