import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';
import Toast from '@components/Toast';

export default function ManageCommissioners() {
  const [commissioners, setCommissioners] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [invite, setInvite] = useState({
    username: '',
    email: '',
    league_id: '',
  });

  const showToast = (message, type) => {
    setToast({ message, type });
  };

  const fetchCommissioners = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/admin/tools/commissioners');
      setCommissioners(res.data);
    } catch {
      // error handled generically; avoid unused variable warning
      showToast('Failed to fetch commissioners', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCommissioners();
  }, [fetchCommissioners]);

  const inviteCommissioner = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post('/admin/tools/commissioners', invite);
      showToast(res.data.message || 'Commissioner invited!', 'success');
      setInvite({ username: '', email: '', league_id: '' });
      fetchCommissioners();
    } catch {
      showToast('Invite failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const removeCommissioner = async (id) => {
    if (!window.confirm('Remove commissioner access?')) return;
    setLoading(true);
    try {
      await apiClient.delete(`/admin/tools/commissioners/${id}`);
      showToast('Commissioner access removed.', 'success');
      fetchCommissioners();
    } catch {
      showToast('Failed to remove commissioner', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto text-white min-h-screen">
      <h2 className="text-2xl font-bold mb-4">Manage Commissioners</h2>
      <div className="mb-6">
        <input
          type="text"
          placeholder="Username"
          value={invite.username}
          onChange={(e) => setInvite({ ...invite, username: e.target.value })}
          className="mr-2 p-2 rounded bg-slate-800 text-white"
        />
        <input
          type="email"
          placeholder="Email"
          value={invite.email}
          onChange={(e) => setInvite({ ...invite, email: e.target.value })}
          className="mr-2 p-2 rounded bg-slate-800 text-white"
        />
        <input
          type="text"
          placeholder="League ID (optional)"
          value={invite.league_id}
          onChange={(e) => setInvite({ ...invite, league_id: e.target.value })}
          className="mr-2 p-2 rounded bg-slate-800 text-white"
        />
        <button
          onClick={inviteCommissioner}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded"
        >
          Invite Commissioner
        </button>
      </div>
      <ul className="divide-y divide-slate-700">
        {commissioners.map((c) => (
          <li key={c.id} className="py-3 flex items-center justify-between">
            <span>
              <strong>{c.username}</strong> ({c.email || 'No email'})
              {c.league_id && (
                <span className="ml-2 text-xs text-slate-400">
                  League: {c.league_id}
                </span>
              )}
              {c.is_superuser && (
                <span className="ml-2 text-xs text-yellow-400">Superuser</span>
              )}
            </span>
            {!c.is_superuser && (
              <button
                onClick={() => removeCommissioner(c.id)}
                className="bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded"
                disabled={loading}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
