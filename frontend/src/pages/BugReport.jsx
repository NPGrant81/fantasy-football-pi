import { useEffect, useState } from 'react';
import apiClient from '@api/client';

export default function BugReport() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [saveEmail, setSaveEmail] = useState(true);
  const [status, setStatus] = useState({ type: '', message: '' });

  useEffect(() => {
    apiClient
      .get('/auth/me')
      .then((res) => {
        setContactEmail(res.data.email || '');
      })
      .catch(() => {
        setContactEmail('');
      });
  }, []);

  const pageUrl = window.location.pathname;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: '', message: '' });

    try {
      if (saveEmail && contactEmail) {
        await apiClient.put('/auth/email', { email: contactEmail });
      }

      await apiClient.post('/feedback/bug', {
        title,
        description,
        page_url: pageUrl,
        severity: severity || null,
        contact_email: contactEmail || null,
      });

      setTitle('');
      setDescription('');
      setSeverity('');
      setStatus({ type: 'success', message: 'Bug report submitted. Thank you!' });
    } catch (err) {
      const detail = err.response?.data?.detail || 'Unable to submit report.';
      setStatus({ type: 'error', message: detail });
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-6 shadow-xl">
        <h1 className="text-2xl font-black text-white uppercase tracking-tight">
          Bug Report
        </h1>
        <p className="text-slate-400 mt-2">
          Tell us what went wrong and where it happened. We will send reports to
          support and log them for review.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 shadow-xl space-y-5"
      >
        {status.message && (
          <div
            className={`rounded-lg px-4 py-3 text-sm font-bold ${
              status.type === 'success'
                ? 'bg-green-900/40 text-green-300 border border-green-700'
                : 'bg-red-900/40 text-red-300 border border-red-700'
            }`}
          >
            {status.message}
          </div>
        )}

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Title
          </label>
          <input
            className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-white focus:border-yellow-500 outline-none"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short summary of the issue"
            required
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Description
          </label>
          <textarea
            className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-white focus:border-yellow-500 outline-none min-h-[140px]"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Steps to reproduce, expected behavior, and what happened"
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
              Severity
            </label>
            <select
              className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-white focus:border-yellow-500 outline-none"
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
            >
              <option value="">Select severity</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
              Page
            </label>
            <input
              className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-slate-400"
              value={pageUrl}
              readOnly
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Contact Email
          </label>
          <input
            className="w-full p-3 rounded bg-slate-950 border border-slate-700 text-white focus:border-yellow-500 outline-none"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            placeholder="you@example.com"
          />
          <label className="flex items-center gap-2 text-xs text-slate-400 mt-2">
            <input
              type="checkbox"
              checked={saveEmail}
              onChange={(e) => setSaveEmail(e.target.checked)}
            />
            Save this email to my profile for future reports
          </label>
        </div>

        <button
          type="submit"
          className="w-full bg-gradient-to-r from-yellow-600 to-yellow-500 text-black font-black py-3 rounded-lg shadow-lg hover:shadow-yellow-600/30 transition"
        >
          Submit Bug Report
        </button>
      </form>
    </div>
  );
}
