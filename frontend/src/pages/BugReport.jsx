import { useEffect, useMemo, useState } from 'react';
import apiClient from '@api/client';
import {
  buttonPrimary,
  cardSurface,
  inputBase,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
} from '@utils/uiStandards';

const PAGE_MAP = {
  '/': 'Home',
  '/draft': 'Draft',
  '/team': 'My Team',
  '/matchups': 'Matchups',
  '/waivers': 'Waiver Wire',
  '/commissioner': 'Commissioner',
  '/admin': 'Admin',
  '/bug-report': 'Bug Report',
};

export default function BugReport() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [issueType, setIssueType] = useState('bug');
  const [contactEmail, setContactEmail] = useState('');
  const [saveEmail, setSaveEmail] = useState(true);
  const [status, setStatus] = useState({ type: '', message: '', issueUrl: '' });

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
  const defaultPageName = PAGE_MAP[pageUrl] || 'Other';
  const [pageName, setPageName] = useState(defaultPageName);
  const pageOptions = useMemo(
    () => [
      'Home',
      'Draft',
      'My Team',
      'Matchups',
      'Game Center',
      'Waiver Wire',
      'Commissioner',
      'Admin',
      'Bug Report',
      'Other',
    ],
    []
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: '', message: '', issueUrl: '' });

    try {
      if (saveEmail && contactEmail) {
        await apiClient.put('/auth/email', { email: contactEmail });
      }

      const response = await apiClient.post('/feedback/bug', {
        title,
        description,
        page_name: pageName || null,
        issue_type: issueType || null,
        page_url: pageUrl,
        contact_email: contactEmail || null,
      });

      setTitle('');
      setDescription('');
      setIssueType('bug');
      const issueUrl = response.data?.issue_url || '';
      const issueWarning = response.data?.issue_warning || '';
      if (issueWarning) {
        setStatus({
          type: 'warning',
          message: `Bug report submitted. ${issueWarning} You can still track the report in-app and create a GitHub issue manually if needed.`,
          issueUrl,
        });
      } else {
        setStatus({
          type: 'success',
          message: issueUrl
            ? 'Bug report submitted and GitHub issue created. Thank you!'
            : 'Bug report submitted. Thank you!',
          issueUrl,
        });
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Unable to submit report.';
      setStatus({ type: 'error', message: detail, issueUrl: '' });
    }
  };

  return (
    <div className={pageShell}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Bug Report</h1>
        <p className={`${pageSubtitle} mt-2`}>
          Tell us what went wrong and where it happened. We will open a GitHub
          issue and log the report for review.
        </p>
      </div>

      <form onSubmit={handleSubmit} className={`${cardSurface} space-y-5`}>
        {status.message && (
          <div
            className={`rounded-lg px-4 py-3 text-sm font-bold ${
              status.type === 'success'
                ? 'bg-green-900/40 text-green-300 border border-green-700'
                : status.type === 'warning'
                ? 'bg-amber-900/40 text-amber-300 border border-amber-700'
                : 'bg-red-900/40 text-red-300 border border-red-700'
            }`}
          >
            {status.message}
            {status.issueUrl && (
              <div className="mt-2 text-xs font-semibold">
                <a
                  href={status.issueUrl}
                  className="underline text-yellow-200"
                  target="_blank"
                  rel="noreferrer"
                >
                  View GitHub issue
                </a>
              </div>
            )}
          </div>
        )}

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Title
          </label>
          <input
            className={inputBase}
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
            className={`${inputBase} min-h-[140px]`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Steps to reproduce, expected behavior, and what happened"
            required
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
              Page Name
            </label>
            <select
              className={inputBase}
              value={pageName}
              onChange={(e) => setPageName(e.target.value)}
            >
              <option value="">Select page</option>
              {pageOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
              Issue Type
            </label>
            <select
              className={inputBase}
              value={issueType}
              onChange={(e) => setIssueType(e.target.value)}
            >
              <option value="bug">Bug</option>
              <option value="feature">Feature</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Page URL
          </label>
          <input
            className={`${inputBase} text-slate-500 dark:text-slate-400`}
            value={pageUrl}
            readOnly
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
            Contact Email
          </label>
          <input
            className={inputBase}
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

        <button type="submit" className={`${buttonPrimary} w-full`}>
          Submit Bug Report
        </button>
      </form>
    </div>
  );
}
