import React, { useEffect, useState } from 'react';
import apiClient from '@api/client';

const defaultRule = {
  event: '',
  range: '',
  value: '',
  positions: '',
};

export default function ManageScoringRules() {
  const [rules, setRules] = useState([]);
  const [form, setForm] = useState(defaultRule);
  const [editingIndex, setEditingIndex] = useState(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // Fetch rules from backend (replace with real API call)
  useEffect(() => {
    async function fetchRules() {
      setLoading(true);
      setMessage('');
      try {
        // Replace with real endpoint
        // const res = await apiClient.get('/scoring/rules');
        // setRules(res.data);
        // Demo: load from CSV (see scoring_logic.csv)
        setRules([
          {
            event: 'Number of Passing TDs',
            range: '1-999',
            value: '6 points each',
            positions: 'QB, RB, WR, TE',
          },
          {
            event: 'Passing Yards',
            range: '1-999',
            value: '.10 points each',
            positions: 'QB, RB, WR, TE',
          },
          {
            event: 'Number of Rushing TDs',
            range: '1-999',
            value: '10 points each',
            positions: 'QB, RB, WR, TE',
          },
        ]);
      } catch (err) {
        setMessage('Failed to load scoring rules');
      } finally {
        setLoading(false);
      }
    }
    fetchRules();
  }, []);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setMessage('');
    if (!form.event || !form.range || !form.value || !form.positions) {
      setMessage('All fields are required.');
      return;
    }
    if (editingIndex !== null) {
      // Edit existing rule
      const updated = [...rules];
      updated[editingIndex] = form;
      setRules(updated);
      setEditingIndex(null);
      setMessage('Rule updated!');
    } else {
      // Add new rule
      setRules([...rules, form]);
      setMessage('Rule added!');
    }
    setForm(defaultRule);
  };

  const handleEdit = (idx) => {
    setForm(rules[idx]);
    setEditingIndex(idx);
  };

  const handleDelete = (idx) => {
    setRules(rules.filter((_, i) => i !== idx));
    setMessage('Rule deleted.');
    setForm(defaultRule);
    setEditingIndex(null);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto text-white min-h-screen">
      <h1 className="text-3xl font-black mb-6">Manage Scoring Rules</h1>
      <form
        onSubmit={handleSubmit}
        className="mb-8 bg-slate-800 p-6 rounded-xl shadow"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            name="event"
            value={form.event}
            onChange={handleChange}
            placeholder="Event"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <input
            name="range"
            value={form.range}
            onChange={handleChange}
            placeholder="Range (e.g. 1-999)"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <input
            name="value"
            value={form.value}
            onChange={handleChange}
            placeholder="Point Value"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <input
            name="positions"
            value={form.positions}
            onChange={handleChange}
            placeholder="Positions (e.g. QB, RB)"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
        </div>
        <button
          type="submit"
          className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded mr-4"
        >
          {editingIndex !== null ? 'Update Rule' : 'Add Rule'}
        </button>
        {editingIndex !== null && (
          <button
            type="button"
            className="bg-slate-700 hover:bg-slate-600 text-white font-bold py-2 px-6 rounded"
            onClick={() => {
              setForm(defaultRule);
              setEditingIndex(null);
            }}
          >
            Cancel
          </button>
        )}
        {message && <div className="mt-4 text-blue-300">{message}</div>}
      </form>
      <div className="bg-slate-900 p-6 rounded-xl shadow">
        <h2 className="text-xl font-bold mb-4">Current Scoring Rules</h2>
        {loading ? (
          <div>Loading...</div>
        ) : rules.length === 0 ? (
          <div className="text-slate-400">No scoring rules set.</div>
        ) : (
          <table className="w-full text-left border-separate border-spacing-y-2">
            <thead>
              <tr className="text-slate-400 text-sm">
                <th>Event</th>
                <th>Range</th>
                <th>Value</th>
                <th>Positions</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, idx) => (
                <tr key={idx} className="bg-slate-800 hover:bg-slate-700">
                  <td>{rule.event}</td>
                  <td>{rule.range}</td>
                  <td>{rule.value}</td>
                  <td>{rule.positions}</td>
                  <td>
                    <button
                      className="bg-yellow-600 hover:bg-yellow-500 text-white font-bold py-1 px-4 rounded mr-2"
                      onClick={() => handleEdit(idx)}
                    >
                      Edit
                    </button>
                    <button
                      className="bg-red-600 hover:bg-red-500 text-white font-bold py-1 px-4 rounded"
                      onClick={() => handleDelete(idx)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
// ...existing code...
