import React, { useEffect, useState } from 'react';
import {
  buttonDanger,
  buttonPrimary,
  buttonSecondary,
  cardSurface,
  inputBase,
  pageHeader,
  pageShell,
  pageSubtitle,
  pageTitle,
  tableHead,
  tableSurface,
} from '@utils/uiStandards';

const defaultRule = {
  category: '',
  event_name: '',
  description: '',
  range_min: '',
  range_max: '',
  point_value: '',
  calculation_type: 'flat_bonus',
  applicable_positions: '',
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
            category: 'passing',
            event_name: 'Number of Passing TDs',
            description: 'Number of Passing TDs',
            range_min: 1,
            range_max: 999,
            point_value: 6,
            calculation_type: 'flat_bonus',
            applicable_positions: 'QB, RB, WR, TE',
          },
          {
            category: 'passing',
            event_name: 'Passing Yards',
            description: 'Passing Yards',
            range_min: 1,
            range_max: 999,
            point_value: 0.1,
            calculation_type: 'per_unit',
            applicable_positions: 'QB, RB, WR, TE',
          },
          {
            category: 'rushing',
            event_name: 'Number of Rushing TDs',
            description: 'Number of Rushing TDs',
            range_min: 1,
            range_max: 999,
            point_value: 10,
            calculation_type: 'flat_bonus',
            applicable_positions: 'QB, RB, WR, TE',
          },
        ]);
      } catch {
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
    if (
      !form.category ||
      !form.event_name ||
      !form.point_value ||
      !form.applicable_positions
    ) {
      setMessage('Required fields missing.');
      return;
    }
    if (
      form.range_min !== '' &&
      form.range_max !== '' &&
      Number(form.range_min) > Number(form.range_max)
    ) {
      setMessage('Range min must be <= max.');
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
    <div className={`${pageShell} min-h-screen`}>
      <div className={pageHeader}>
        <h1 className={pageTitle}>Manage Scoring Rules</h1>
        <p className={pageSubtitle}>
          Configure scoring events, ranges, and point values.
        </p>
      </div>
      <form onSubmit={handleSubmit} className={`${cardSurface} mb-0`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            name="category"
            value={form.category}
            onChange={handleChange}
            placeholder="Category"
            className={inputBase}
          />
          <input
            name="event_name"
            value={form.event_name}
            onChange={handleChange}
            placeholder="Event Name"
            className={inputBase}
          />
          <input
            name="description"
            value={form.description}
            onChange={handleChange}
            placeholder="Description"
            className={inputBase}
          />
          <div className="flex gap-2">
            <input
              name="range_min"
              value={form.range_min}
              onChange={handleChange}
              placeholder="Min"
              className={`${inputBase} flex-1`}
            />
            <input
              name="range_max"
              value={form.range_max}
              onChange={handleChange}
              placeholder="Max"
              className={`${inputBase} flex-1`}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            name="point_value"
            value={form.point_value}
            onChange={handleChange}
            placeholder="Point Value"
            className={inputBase}
          />
          <select
            name="calculation_type"
            value={form.calculation_type}
            onChange={handleChange}
            className={inputBase}
          >
            <option value="flat_bonus">Flat Bonus</option>
            <option value="per_unit">Per Unit</option>
          </select>
          <input
            name="applicable_positions"
            value={form.applicable_positions}
            onChange={handleChange}
            placeholder="Positions (comma-separated)"
            className={inputBase}
          />
          {/* empty slot to keep grid aligned */}
          <div />
        </div>
        <button type="submit" className={`${buttonPrimary} mr-4`}>
          {editingIndex !== null ? 'Update Rule' : 'Add Rule'}
        </button>
        {editingIndex !== null && (
          <button
            type="button"
            className={buttonSecondary}
            onClick={() => {
              setForm(defaultRule);
              setEditingIndex(null);
            }}
          >
            Cancel
          </button>
        )}
        {message && <div className="mt-4 text-sm text-cyan-300">{message}</div>}
      </form>
      <div className={cardSurface}>
        <h2 className="mb-4 text-lg font-bold text-slate-900 dark:text-white">
          Current Scoring Rules
        </h2>
        {loading ? (
          <div className="text-slate-600 dark:text-slate-400">Loading...</div>
        ) : rules.length === 0 ? (
          <div className="text-slate-600 dark:text-slate-400">
            No scoring rules set.
          </div>
        ) : (
          <div className={tableSurface}>
            <table className="w-full text-left text-sm text-slate-700 dark:text-slate-300">
              <thead className={tableHead}>
                <tr>
                  <th>Category</th>
                  <th>Event</th>
                  <th>Range</th>
                  <th>Value</th>
                  <th>Type</th>
                  <th>Positions</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule, idx) => (
                  <tr
                    key={idx}
                    className="border-t border-slate-300 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/40"
                  >
                    <td>{rule.category}</td>
                    <td>{rule.event_name}</td>
                    <td>
                      {rule.range_min}-{rule.range_max}
                    </td>
                    <td>{rule.point_value}</td>
                    <td>{rule.calculation_type}</td>
                    <td>{rule.applicable_positions}</td>
                    <td>
                      <button
                        className={`${buttonSecondary} mr-2 px-3 py-1 text-xs`}
                        onClick={() => handleEdit(idx)}
                      >
                        Edit
                      </button>
                      <button
                        className={`${buttonDanger} px-3 py-1 text-xs`}
                        onClick={() => handleDelete(idx)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
// ...existing code...
