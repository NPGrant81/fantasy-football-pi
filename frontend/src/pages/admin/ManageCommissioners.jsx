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
} from '../../utils/uiStandards';

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
      <div className={pageShell}>
        <LoadingState message="Loading commissioner management..." className="mt-20" />
      </div>
    );
  }

  return (
    <PageTemplate
      title="Invite / Manage Commissioners"
      subtitle="Invite commissioners, update account details, assign league IDs, and remove commissioner access."
      actions={
        <Link
          to="/admin"
          className={`${buttonSecondary} gap-2 px-3 py-2 text-sm no-underline`}
        >
          <FiChevronLeft /> Back
        </Link>
      }
    >

      {error ? <ErrorState message={error} className="mb-4" /> : null}
      {notice && (
        <div className="mb-4 rounded-lg border border-green-800/60 bg-green-900/20 p-3 text-sm text-green-200">
          {notice}
        </div>
      )}

      <div className={`${cardSurface} mb-0`}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Invite New Commissioner
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Commissioner name"
            className={inputBase}
          />
          <input
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="Email address"
            className={inputBase}
          />
          <input
            value={newLeagueId}
            onChange={(e) => setNewLeagueId(e.target.value)}
            placeholder="League ID (optional)"
            className={inputBase}
          />
          <button
            onClick={addCommissioner}
            disabled={saving}
            className={`${buttonPrimary} gap-2 ${saving ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <FiUserPlus /> Send Invite
          </button>
        </div>
      </div>

      <div className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Current Commissioners
        </h2>
        <StandardTableContainer>
          <StandardTable>
            <StandardTableHead
              headers={[
                { key: 'name', label: 'Name', className: 'px-3 py-3' },
                { key: 'email', label: 'Email', className: 'px-3 py-3' },
                { key: 'league', label: 'League ID', className: 'px-3 py-3' },
                { key: 'actions', label: 'Actions', className: 'px-3 py-3' },
              ]}
            />
            <tbody>
              {commissioners.map((commissioner) => (
                <StandardTableRow key={commissioner.id}>
                  <td className={tableCell}>
                    <input
                      value={commissioner.username || ''}
                      onChange={(e) =>
                        updateField(commissioner.id, 'username', e.target.value)
                      }
                      className={`${inputBase} py-1`}
                    />
                  </td>
                  <td className={tableCell}>
                    <input
                      value={commissioner.email || ''}
                      onChange={(e) =>
                        updateField(commissioner.id, 'email', e.target.value)
                      }
                      className={`${inputBase} py-1`}
                    />
                  </td>
                  <td className={tableCell}>
                    <input
                      value={commissioner.league_id ?? ''}
                      onChange={(e) =>
                        updateField(
                          commissioner.id,
                          'league_id',
                          e.target.value
                        )
                      }
                      className={`${inputBase} py-1`}
                    />
                  </td>
                  <td className={tableCell}>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => saveCommissioner(commissioner)}
                        disabled={saving || !commissioner._dirty}
                        className={`${saving || !commissioner._dirty ? `${buttonSecondary} opacity-50 cursor-not-allowed` : buttonPrimary} gap-1 px-2 py-1 text-xs`}
                      >
                        <FiSave /> Update
                      </button>
                      <button
                        onClick={() => removeCommissioner(commissioner)}
                        disabled={saving || commissioner.is_superuser}
                        className={`${saving || commissioner.is_superuser ? `${buttonSecondary} opacity-50 cursor-not-allowed` : buttonDanger} gap-1 px-2 py-1 text-xs`}
                      >
                        <FiTrash2 /> Remove Access
                      </button>
                      <span className={`inline-flex items-center gap-1 ${textCaption}`}>
                        <FiMail /> invite/login details sent on add
                      </span>
                    </div>
                  </td>
                </StandardTableRow>
              ))}
            </tbody>
          </StandardTable>
        </StandardTableContainer>
      </div>

      {dirtyRows.length > 0 && (
        <p className="text-xs text-orange-600 dark:text-orange-300">
          {dirtyRows.length} commissioner row(s) have unsaved edits.
        </p>
      )}
    </PageTemplate>
  );
}
