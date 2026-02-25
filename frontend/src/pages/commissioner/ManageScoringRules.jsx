import React, { useEffect, useState } from 'react';

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
            point_value: 0.10,
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
    if (form.range_min !== '' && form.range_max !== '' && Number(form.range_min) > Number(form.range_max)) {
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
    <div className="p-8 max-w-4xl mx-auto text-white min-h-screen">
      <h1 className="text-3xl font-black mb-6">Manage Scoring Rules</h1>
      <form
        onSubmit={handleSubmit}
        className="mb-8 bg-slate-800 p-6 rounded-xl shadow"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            name="category"
            value={form.category}
            onChange={handleChange}
            placeholder="Category"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <input
            name="event_name"
            value={form.event_name}
            onChange={handleChange}
            placeholder="Event Name"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <input
            name="description"
            value={form.description}
            onChange={handleChange}
            placeholder="Description"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <div className="flex gap-2">
            <input
              name="range_min"
              value={form.range_min}
              onChange={handleChange}
              placeholder="Min"
              className="p-2 rounded bg-slate-900 text-white border border-slate-700 flex-1"
            />
            <input
              name="range_max"
              value={form.range_max}
              onChange={handleChange}
              placeholder="Max"
              className="p-2 rounded bg-slate-900 text-white border border-slate-700 flex-1"
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <input
            name="point_value"
            value={form.point_value}
            onChange={handleChange}
            placeholder="Point Value"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          <select
            name="calculation_type"
            value={form.calculation_type}
            onChange={handleChange}
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          >
            <option value="flat_bonus">Flat Bonus</option>
            <option value="per_unit">Per Unit</option>
          </select>
          <input
            name="applicable_positions"
            value={form.applicable_positions}
            onChange={handleChange}
            placeholder="Positions (comma-separated)"
            className="p-2 rounded bg-slate-900 text-white border border-slate-700"
          />
          {/* empty slot to keep grid aligned */}
          <div />
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
                <tr key={idx} className="bg-slate-800 hover:bg-slate-700">
                  <td>{rule.category}</td>
                  <td>{rule.event_name}</td>
                  <td>{rule.range_min}-{rule.range_max}</td>
                  <td>{rule.point_value}</td>
                  <td>{rule.calculation_type}</td>
                  <td>{rule.applicable_positions}</td>
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
