import { useEffect, useState } from 'react'
import axios from 'axios'
import { 
    FiSettings, FiUsers, FiShield, FiChevronLeft, FiSave, 
    FiPlus, FiTrash2, FiUserPlus, FiUserX, FiActivity, FiUserCheck 
} from 'react-icons/fi'

// --- SCORING MENU (Keep your full list here) ---
const SCORING_MENU = {
  Passing: [
    "Passing TD (6 pts)", "Bonus: Pass TD Length (30-39 yds)", "Bonus: Pass TD Length (40-49 yds)", "Bonus: Pass TD Length (50+ yds)",
    "Passing Yards (0.1 pt per yard)", "Bonus: Passing Yards (200-249)", "Bonus: Passing Yards (250-299)", "Bonus: Passing Yards (300-349)",
    "Bonus: Passing Yards (350-399)", "Bonus: Passing Yards (400+)", "Pass Completions (0.5 pt each)", "Bonus: Pass Completions (30+ in game)",
    "Interception Thrown (-3 pts)", "2-Pt Conversion (Pass)"
  ],
  Rushing: [
    "Rushing TD (10 pts)", "Bonus: Rush TD Length (30-39 yds)", "Bonus: Rush TD Length (40-49 yds)", "Bonus: Rush TD Length (50+ yds)",
    "Rushing Yards (0.3 pt per yard)", "Bonus: Rushing Yards (100-109)", "Bonus: Rushing Yards (110-119)", "Bonus: Rushing Yards (120-129)",
    "Bonus: Rushing Yards (130-139)", "Bonus: Rushing Yards (140-149)", "Bonus: Rushing Yards (150-174)", "Bonus: Rushing Yards (175-199)",
    "Bonus: Rushing Yards (200+)", "Rush Attempts (0.5 pt each)", "Bonus: Rush Attempts (25+ in game)", "2-Pt Conversion (Run)", "Fumble Lost (-4 pts)"
  ],
  Receiving: [
    "Receiving TD (10 pts)", "Bonus: Rec TD Length (30-39 yds)", "Bonus: Rec TD Length (40-49 yds)", "Bonus: Rec TD Length (50+ yds)",
    "Receiving Yards (0.3 pt per yard)", "Bonus: Receiving Yards (100-109)", "Bonus: Receiving Yards (110-119)", "Bonus: Receiving Yards (120-129)",
    "Bonus: Receiving Yards (130-139)", "Bonus: Receiving Yards (140-149)", "Bonus: Receiving Yards (150-174)", "Bonus: Receiving Yards (175-199)",
    "Bonus: Receiving Yards (200+)", "Receptions (3 pts each)", "Bonus: Receptions (10+ in game)", "2-Pt Conversion (Catch)"
  ],
  Kicking: [
    "Field Goal Made (3 pts)", "Bonus: FG Length (50+)", "Field Goal Missed (-1 pt)", "PAT Made (1 pt)", "PAT Missed (-1 pt)"
  ],
  Defense: [
    "Sack (1 pt)", "Interception Caught (2 pts)", "Fumble Recovery (3 pts)", "Safety (2 pts)", "Blocked Kick (FG/Punt/PAT) (2 pts)",
    "Defensive/ST TD (6 pts)", "Points Allowed (0) (15 pts)", "Points Allowed (1-6) (10 pts)", "Points Allowed (7-13) (7 pts)",
    "Points Allowed (14-20) (5 pts)", "Points Allowed (21-27) (1 pt)", "Yards Allowed (0-149) (15 pts)", "Yards Allowed (150-199) (10 pts)",
    "Yards Allowed (200-249) (7 pts)", "Yards Allowed (250-299) (5 pts)", "Yards Allowed (300-349) (1 pt)"
  ],
  SpecialTeams: [
    "Punt Return TD (10 pts)", "Punt Return Yards (1 pt per 25)", "Kickoff Return TD (10 pts)", "Kickoff Return Yards (1 pt per 25)"
  ]
}

export default function CommissionerDashboard({ token }) {
  const [view, setView] = useState('menu') 
  const [settings, setSettings] = useState(null)
  const [allUsers, setAllUsers] = useState([]) 
  const [loading, setLoading] = useState(true)
  const [unsavedChanges, setUnsavedChanges] = useState(false)
  const [activeTab, setActiveTab] = useState('Passing') 
  
  // New State for Creating User
  const [newOwnerName, setNewOwnerName] = useState('')

  const leagueId = localStorage.getItem('fantasyLeagueId')

  const loadData = () => {
    if (token && leagueId) {
        setLoading(true)
        axios.get(`http://127.0.0.1:8000/leagues/${leagueId}/settings`, { headers: { Authorization: `Bearer ${token}` } })
        .then(res => setSettings(res.data))
        .catch(err => console.error(err))

        axios.get('http://127.0.0.1:8000/owners', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => setAllUsers(res.data))
        .finally(() => setLoading(false))
    }
  }

  useEffect(() => { loadData() }, [token, leagueId])

  // --- HANDLERS ---
  const handleUpdate = (field, value) => { setSettings({ ...settings, [field]: value }); setUnsavedChanges(true); }
  const handleRuleChange = (idx, field, val) => { const n = [...settings.scoring_rules]; n[idx][field] = val; setSettings({ ...settings, scoring_rules: n }); setUnsavedChanges(true); }
  const addRule = () => { const evt = SCORING_MENU[activeTab] ? SCORING_MENU[activeTab][0] : "New Rule"; setSettings({ ...settings, scoring_rules: [...settings.scoring_rules, { category: activeTab, description: evt, points: 0 }] }); setUnsavedChanges(true); }
  const deleteRule = (idx) => { setSettings({ ...settings, scoring_rules: settings.scoring_rules.filter((_, i) => i !== idx) }); setUnsavedChanges(true); }
  const resetDefaults = () => { if(window.confirm("Wipe all rules?")) { setSettings(prev => ({ ...prev, scoring_rules: [] })); setUnsavedChanges(true); } }
  
  const saveSettings = () => {
    axios.put(`http://127.0.0.1:8000/leagues/${leagueId}/settings`, settings, { headers: { Authorization: `Bearer ${token}` } })
      .then(() => { alert("Saved!"); setUnsavedChanges(false); if(settings.scoring_rules.length === 0) window.location.reload(); })
      .catch(() => alert("Error saving"))
  }

  // --- USER HANDLERS ---
// 1. Add state for email
const [newOwnerEmail, setNewOwnerEmail] = useState('')

// 2. Updated Handler
const handleCreateOwner = () => {
    if(!newOwnerName) return;
    
    // Send both name and email
    axios.post(`http://127.0.0.1:8000/leagues/owners`, 
        { username: newOwnerName, email: newOwnerEmail }, 
        { headers: { Authorization: `Bearer ${token}` } }
    )
    .then((res) => { 
        // Show the password in alert only for testing!
        alert(`User created! \nCheck terminal or email for password.`); 
        setNewOwnerName(''); 
        setNewOwnerEmail(''); 
        loadData(); 
    })
    .catch(err => alert("Error: " + (err.response?.data?.detail || err.message)))
}

  const handleRecruit = (username) => {
    axios.post(`http://127.0.0.1:8000/leagues/${leagueId}/members`, { username }, { headers: { Authorization: `Bearer ${token}` } })
    .then(() => { loadData(); alert(`Recruited ${username}!`) })
  }
  const handleKick = (userId) => {
    if (window.confirm("Kick user?")) {
        axios.delete(`http://127.0.0.1:8000/leagues/${leagueId}/members/${userId}`, { headers: { Authorization: `Bearer ${token}` } })
        .then(() => loadData())
    }
  }

  const activeRules = settings?.scoring_rules?.map((r, i) => ({...r, originalIndex: i})).filter(r => r.category === activeTab) || []
  const myMembers = allUsers.filter(u => u.league_id === parseInt(leagueId))
  const freeAgents = allUsers.filter(u => !u.league_id)

  if (loading) return <div className="text-white text-center mt-20 animate-pulse">Entering The War Room...</div>

  if (view === 'menu') return (
      <div className="p-10 max-w-4xl mx-auto text-white animate-fade-in text-center">
        <h1 className="text-5xl font-black italic tracking-tighter uppercase mb-2">Commissioner Office</h1>
        <p className="text-slate-400 mb-12">Select a module to configure your league.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <button onClick={() => setView('scoring')} className="group bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 hover:border-green-500 p-10 rounded-2xl shadow-2xl transition hover:transform hover:-translate-y-2 flex flex-col items-center gap-4">
                <div className="bg-slate-900 p-6 rounded-full border border-slate-700 group-hover:border-green-500 group-hover:text-green-500 transition"><FiActivity size={48} /></div>
                <div><h2 className="text-2xl font-bold uppercase">Scoring & Settings</h2><p className="text-slate-500 text-sm mt-2">Adjust Roster Size, Salary Cap, and Point Values.</p></div>
            </button>
            <button onClick={() => setView('users')} className="group bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 hover:border-blue-500 p-10 rounded-2xl shadow-2xl transition hover:transform hover:-translate-y-2 flex flex-col items-center gap-4">
                <div className="bg-slate-900 p-6 rounded-full border border-slate-700 group-hover:border-blue-500 group-hover:text-blue-500 transition"><FiUsers size={48} /></div>
                <div><h2 className="text-2xl font-bold uppercase">Manage Owners</h2><p className="text-slate-500 text-sm mt-2">Create new owners, recruit free agents, or kick members.</p></div>
            </button>
        </div>
      </div>
  )

  if (view === 'scoring') return (
    <div className="p-8 pb-20 animate-fade-in space-y-6 text-white max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
            <button onClick={() => setView('menu')} className="flex items-center gap-2 text-slate-400 hover:text-white transition"><FiChevronLeft /> Back to Menu</button>
            <h2 className="text-2xl font-bold uppercase flex items-center gap-2"><FiSettings /> League Settings</h2>
            <div className="flex gap-2">
                <button onClick={resetDefaults} className="bg-slate-800 px-4 py-2 rounded text-sm hover:text-red-400 transition">Reset</button>
                {unsavedChanges && <button onClick={saveSettings} className="bg-green-600 px-6 py-2 rounded font-bold hover:bg-green-500 flex items-center gap-2"><FiSave/> Save</button>}
            </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl">
                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Roster Size</div>
                <input type="number" className="w-full bg-slate-950 border border-slate-700 text-white p-2 rounded font-bold" value={settings.roster_size} onChange={(e) => handleUpdate('roster_size', parseInt(e.target.value))} />
            </div>
            <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl">
                <div className="text-xs font-bold text-slate-500 uppercase mb-2">Salary Cap ($)</div>
                <input type="number" className="w-full bg-slate-950 border border-slate-700 text-white p-2 rounded font-bold" value={settings.salary_cap} onChange={(e) => handleUpdate('salary_cap', parseInt(e.target.value))} />
            </div>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl mt-6">
            <div className="flex bg-slate-950 border-b border-slate-800 overflow-x-auto">
                {Object.keys(SCORING_MENU).map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)} className={`px-6 py-4 font-bold uppercase text-sm tracking-wide transition ${activeTab === tab ? 'bg-slate-800 text-white border-b-2 border-green-500' : 'text-slate-500 hover:text-slate-300'}`}>{tab}</button>
                ))}
            </div>
            <div className="p-6 space-y-2">
                {activeRules.map((rule) => (
                    <div key={rule.originalIndex} className="grid grid-cols-12 gap-4 items-center bg-slate-950/50 p-3 rounded border border-slate-800 hover:border-slate-600 transition">
                        <div className="col-span-8">
                            <select className="w-full bg-slate-900 text-white font-bold outline-none border border-slate-700 rounded p-2 text-sm focus:border-green-500" value={rule.description} onChange={(e) => handleRuleChange(rule.originalIndex, 'description', e.target.value)}>
                                {SCORING_MENU[activeTab]?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                        </div>
                        <div className="col-span-3">
                            <input type="number" className="w-full bg-slate-900 text-center text-green-400 font-bold rounded p-2 border border-slate-700 outline-none focus:border-green-500" value={rule.points} onChange={(e) => handleRuleChange(rule.originalIndex, 'points', parseFloat(e.target.value))} />
                        </div>
                        <div className="col-span-1 text-right">
                            <button onClick={() => deleteRule(rule.originalIndex)} className="text-slate-600 hover:text-red-500 transition px-2"><FiTrash2 /></button>
                        </div>
                    </div>
                ))}
                <button onClick={addRule} className="mt-4 w-full py-3 border-2 border-dashed border-slate-700 text-slate-500 font-bold rounded-xl hover:border-slate-500 hover:text-slate-300 transition flex items-center justify-center gap-2"><FiPlus /> Add {activeTab} Rule</button>
            </div>
        </div>
    </div>
  )

  if (view === 'users') return (
    <div className="p-8 animate-fade-in text-white max-w-5xl mx-auto">
         <div className="flex justify-between items-center mb-8">
            <button onClick={() => setView('menu')} className="flex items-center gap-2 text-slate-400 hover:text-white transition"><FiChevronLeft /> Back to Menu</button>
            <h2 className="text-2xl font-bold uppercase flex items-center gap-2"><FiShield /> Owner Management</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* CREATE OWNER FORM */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl col-span-1 md:col-span-2">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <FiUserPlus className="text-green-400"/> Invite New Owner
                </h3>
                <div className="flex flex-col md:flex-row gap-4 items-end">
                    <div className="flex-grow w-full">
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Owner Name</label>
                        <input className="w-full bg-slate-950 border border-slate-700 text-white p-3 rounded outline-none focus:border-green-500" 
                            placeholder="First_Last" value={newOwnerName} onChange={e => setNewOwnerName(e.target.value)}
                        />
                    </div>
                    <div className="flex-grow w-full">
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Email Address</label>
                        <input className="w-full bg-slate-950 border border-slate-700 text-white p-3 rounded outline-none focus:border-green-500" 
                            placeholder="chesters@example.com" value={newOwnerEmail} onChange={e => setNewOwnerEmail(e.target.value)}
                        />
                    </div>
                    <button onClick={handleCreateOwner} className="bg-green-600 hover:bg-green-500 text-white font-bold px-6 py-3 rounded shadow-lg transition transform hover:scale-105 w-full md:w-auto">
                        SEND INVITE
                    </button>
                </div>
            </div>

            {/* LISTS */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
                <h3 className="text-xl font-bold text-green-400 mb-4 flex items-center gap-2">Active Owners ({myMembers.length})</h3>
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                    {myMembers.map(user => (
                        <div key={user.id} className="flex justify-between items-center bg-slate-950 p-4 rounded border border-green-900/30">
                            <span className="font-bold">{user.username}</span>
                            <button onClick={() => handleKick(user.id)} className="text-slate-500 hover:text-red-500 text-sm font-bold flex items-center gap-1 transition"><FiUserX /> Kick</button>
                        </div>
                    ))}
                </div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
                <h3 className="text-xl font-bold text-blue-400 mb-4 flex items-center gap-2">Free Agents ({freeAgents.length})</h3>
                <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                    {freeAgents.length === 0 && <p className="text-slate-500 italic text-sm">No free agents. Create a new owner above!</p>}
                    {freeAgents.map(user => (
                        <div key={user.id} className="flex justify-between items-center bg-slate-950 p-4 rounded border border-slate-800 opacity-75 hover:opacity-100 transition">
                            <span className="text-slate-300">{user.username}</span>
                            <button onClick={() => handleRecruit(user.username)} className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold px-3 py-2 rounded flex items-center gap-2 transition"><FiUserCheck /> Recruit</button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    </div>
  )
}