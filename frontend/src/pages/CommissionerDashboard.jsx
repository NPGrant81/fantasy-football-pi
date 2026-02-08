import { useEffect, useState } from 'react'
import axios from 'axios'
import { FiSave, FiPlus, FiTrash2, FiSettings, FiDollarSign, FiUsers, FiUserPlus } from 'react-icons/fi'

export default function CommissionerDashboard({ token }) {
  // --- STATE ---
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('Teams') // Default to Teams tab
  const [unsavedChanges, setUnsavedChanges] = useState(false)
  const [allUsers, setAllUsers] = useState([]) 

  // --- LOAD DATA ---
  useEffect(() => {
    if (token) {
      // 1. Get Settings
      axios.get('http://127.0.0.1:8000/league/settings', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => { setSettings(res.data); setLoading(false) })
        .catch(err => alert("Error loading settings"))

      // 2. Get All Users
      axios.get('http://127.0.0.1:8000/league/users', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => setAllUsers(res.data))
        .catch(err => console.error("Error loading users"))
    }
  }, [token])

  // --- HANDLERS ---
  const handleUpdate = (field, value) => {
    setSettings({ ...settings, [field]: value })
    setUnsavedChanges(true)
  }

  const handleRuleChange = (index, field, value) => {
    const newRules = [...settings.scoring_rules]
    newRules[index][field] = value
    setSettings({ ...settings, scoring_rules: newRules })
    setUnsavedChanges(true)
  }

  const addRule = () => {
    const newRule = { cat: activeTab, event: "New Rule", min: 0, max: 999, pts: 0, type: "flat", desc: "Description" }
    setSettings({ ...settings, scoring_rules: [...settings.scoring_rules, newRule] })
    setUnsavedChanges(true)
  }

  const deleteRule = (index) => {
    const newRules = settings.scoring_rules.filter((_, i) => i !== index)
    setSettings({ ...settings, scoring_rules: newRules })
    setUnsavedChanges(true)
  }

  const saveSettings = () => {
    // We need your user_id (Mocking as 1 for Commissioner)
    const payload = { ...settings }
    axios.put('http://127.0.0.1:8000/league/settings?user_id=1', payload, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => {
         alert("✅ Settings Saved Successfully!")
         setUnsavedChanges(false)
      })
      .catch(err => alert("❌ Error saving: " + err.response?.data?.detail))
  }

  const handleRecruit = (userId) => {
    // Assuming logged-in user is ID 1 (Commissioner)
    axios.post(`http://127.0.0.1:8000/league/add-member?current_user_id=1`, 
      { user_id: userId }, 
      { headers: { Authorization: `Bearer ${token}` } }
    )
    .then(res => {
        alert(res.data.message)
        window.location.reload()
    })
    .catch(err => alert("Error moving user: " + err.response?.data?.detail))
  }

  // --- RENDER ---
  if (loading) return <div className="text-white text-center mt-20">Loading Commissioner Tools...</div>

  // Filter Rules by Tab (Only used if not on 'Teams' tab)
  const activeRules = settings?.scoring_rules?.filter(r => r.cat === activeTab) || []

  return (
    <div className="pb-20 animate-fade-in space-y-6">
      
      {/* HEADER */}
      <div className="flex justify-between items-center bg-gradient-to-r from-red-900 to-slate-900 p-6 rounded-xl border border-red-700/50 shadow-2xl">
         <div>
            <h1 className="text-3xl font-black text-white italic tracking-tighter uppercase flex items-center gap-2">
               <FiSettings /> Commissioner Dashboard
            </h1>
            <p className="text-red-200 text-sm mt-1">League Rules & Scoring Engine</p>
         </div>
         {unsavedChanges && (
            <button onClick={saveSettings} className="bg-green-500 hover:bg-green-400 text-black font-bold px-6 py-3 rounded-full flex items-center gap-2 shadow-lg animate-pulse transition">
               <FiSave size={20} /> Save Changes
            </button>
         )}
      </div>

      {/* GLOBAL SETTINGS CARD */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
         <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl">
            <div className="flex items-center gap-2 text-slate-400 uppercase text-xs font-bold mb-2">
               <FiSettings /> League Name
            </div>
            <input 
               className="w-full bg-slate-950 border border-slate-700 text-white p-2 rounded focus:border-red-500 outline-none font-bold"
               value={settings.league_name}
               onChange={(e) => handleUpdate('league_name', e.target.value)}
            />
         </div>
         <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl">
            <div className="flex items-center gap-2 text-slate-400 uppercase text-xs font-bold mb-2">
               <FiUsers /> Roster Size
            </div>
            <input 
               type="number"
               className="w-full bg-slate-950 border border-slate-700 text-white p-2 rounded focus:border-red-500 outline-none font-bold"
               value={settings.roster_size}
               onChange={(e) => handleUpdate('roster_size', parseInt(e.target.value))}
            />
         </div>
         <div className="bg-slate-900 border border-slate-700 p-6 rounded-xl">
            <div className="flex items-center gap-2 text-slate-400 uppercase text-xs font-bold mb-2">
               <FiDollarSign /> Salary Cap
            </div>
            <input 
               type="number"
               className="w-full bg-slate-950 border border-slate-700 text-white p-2 rounded focus:border-red-500 outline-none font-bold"
               value={settings.salary_cap}
               onChange={(e) => handleUpdate('salary_cap', parseInt(e.target.value))}
            />
         </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
         
         {/* TABS */}
         <div className="flex bg-slate-950 border-b border-slate-800 overflow-x-auto">
            {['Teams', 'Passing', 'Rushing', 'Receiving', 'Kicking', 'Defense'].map(tab => (
               <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-6 py-4 font-bold uppercase text-sm tracking-wide transition ${activeTab === tab ? 'bg-slate-800 text-white border-b-2 border-red-500' : 'text-slate-500 hover:text-slate-300'}`}
               >
                  {tab}
               </button>
            ))}
         </div>

         {/* TAB CONTENT */}
         <div className="p-6">
            
            {/* === TEAMS TAB === */}
            {activeTab === 'Teams' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {allUsers.map(user => {
                        // Check if user is in YOUR league (Assuming ID 1 for now)
                        const isMyLeague = user.league_id === 1; 

                        return (
                            <div key={user.id} className={`p-4 rounded-xl border flex justify-between items-center ${isMyLeague ? 'bg-blue-900/20 border-blue-500/50' : 'bg-slate-950 border-slate-800'}`}>
                                <div>
                                    <div className="font-bold text-white">{user.username}</div>
                                    <div className="text-xs text-slate-500">
                                        {isMyLeague ? "✅ In your league" : `Currently in League #${user.league_id || 'None'}`}
                                    </div>
                                </div>
                                {!isMyLeague && (
                                    <button 
                                        onClick={() => handleRecruit(user.id)}
                                        className="bg-green-600 hover:bg-green-500 text-white text-xs font-bold px-3 py-2 rounded flex items-center gap-2 transition"
                                    >
                                        <FiUserPlus /> RECRUIT
                                    </button>
                                )}
                            </div>
                        )
                    })}
                </div>
            ) : (
                /* === SCORING RULES TAB === */
                <>
                    <div className="grid grid-cols-12 gap-4 mb-4 text-xs font-bold text-slate-500 uppercase tracking-wider px-2">
                        <div className="col-span-3">Event Name</div>
                        <div className="col-span-2 text-center">Min Range</div>
                        <div className="col-span-2 text-center">Max Range</div>
                        <div className="col-span-2 text-center">Points</div>
                        <div className="col-span-2 text-center">Type</div>
                        <div className="col-span-1"></div>
                    </div>

                    <div className="space-y-2">
                        {activeRules.map((rule) => {
                            const globalIndex = settings.scoring_rules.indexOf(rule)
                            return (
                                <div key={globalIndex} className="grid grid-cols-12 gap-4 items-center bg-slate-950/50 p-3 rounded border border-slate-800 hover:border-slate-600 transition">
                                    {/* Event Name */}
                                    <div className="col-span-3">
                                        <input className="w-full bg-transparent text-white font-bold outline-none border-b border-transparent focus:border-slate-500 text-sm" 
                                            value={rule.event} 
                                            onChange={(e) => handleRuleChange(globalIndex, 'event', e.target.value)} 
                                        />
                                        <input className="w-full bg-transparent text-slate-500 text-[10px] outline-none" 
                                            value={rule.desc} 
                                            onChange={(e) => handleRuleChange(globalIndex, 'desc', e.target.value)} 
                                        />
                                    </div>
                                    {/* Range Min */}
                                    <div className="col-span-2">
                                        <input type="number" className="w-full bg-slate-900 text-center text-slate-300 rounded p-1 border border-slate-700" 
                                            value={rule.min} 
                                            onChange={(e) => handleRuleChange(globalIndex, 'min', parseFloat(e.target.value))} 
                                        />
                                    </div>
                                    {/* Range Max */}
                                    <div className="col-span-2">
                                        <input type="number" className="w-full bg-slate-900 text-center text-slate-300 rounded p-1 border border-slate-700" 
                                            value={rule.max} 
                                            onChange={(e) => handleRuleChange(globalIndex, 'max', parseFloat(e.target.value))} 
                                        />
                                    </div>
                                    {/* Points */}
                                    <div className="col-span-2">
                                        <input type="number" className="w-full bg-slate-900 text-center text-green-400 font-bold rounded p-1 border border-slate-700" 
                                            value={rule.pts} 
                                            onChange={(e) => handleRuleChange(globalIndex, 'pts', parseFloat(e.target.value))} 
                                        />
                                    </div>
                                    {/* Type */}
                                    <div className="col-span-2 text-center">
                                        <select className="bg-slate-900 text-xs text-slate-400 p-1 rounded border border-slate-700"
                                            value={rule.type}
                                            onChange={(e) => handleRuleChange(globalIndex, 'type', e.target.value)}
                                        >
                                            <option value="per_unit">Per Unit</option>
                                            <option value="flat">Flat Bonus</option>
                                        </select>
                                    </div>
                                    {/* Delete */}
                                    <div className="col-span-1 text-right">
                                        <button onClick={() => deleteRule(globalIndex)} className="text-slate-600 hover:text-red-500 transition">
                                            <FiTrash2 />
                                        </button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>

                    <button onClick={addRule} className="mt-4 w-full py-3 border-2 border-dashed border-slate-700 text-slate-500 font-bold rounded-xl hover:border-slate-500 hover:text-slate-300 transition flex items-center justify-center gap-2">
                        <FiPlus /> Add Scoring Rule
                    </button>
                </>
            )}
         </div>
      </div>
    </div>
  )
}