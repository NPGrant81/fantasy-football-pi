import { useEffect, useState, useCallback } from 'react'
import axios from 'axios'
import { 
    FiSettings, FiUsers, FiShield, FiChevronLeft, FiSave, 
    FiPlus, FiTrash2, FiUserPlus, FiUserX, FiActivity, FiUserCheck 
} from 'react-icons/fi'

// --- 2.1 MOVE STATIC DATA AND HELPERS OUTSIDE ---
const SCORING_MENU = {
  Passing: ["Passing TD (6 pts)", "Bonus: Pass TD Length (40-49 yds)", "Passing Yards (0.1 pt per yard)"],
  Rushing: ["Rushing TD (10 pts)", "Rushing Yards (0.3 pt per yard)"],
  // ... (keep your full list here)
}

export default function CommissionerDashboard({ token }) {
  const [view, setView] = useState('menu') 
  const [settings, setSettings] = useState(null)
  const [allUsers, setAllUsers] = useState([]) 
  const [loading, setLoading] = useState(true)
  const [unsavedChanges, setUnsavedChanges] = useState(false)
  const [activeTab, setActiveTab] = useState('Passing') 
  const [newOwnerName, setNewOwnerName] = useState('')
  const [newOwnerEmail, setNewOwnerEmail] = useState('')

  const leagueId = localStorage.getItem('fantasyLeagueId')

  // 2.2 Wrap loadData in useCallback to prevent re-renders
  const loadData = useCallback(() => {
    if (token && leagueId) {
      setLoading(true)
      const settingsReq = axios.get(`http://127.0.0.1:8000/leagues/${leagueId}/settings`, { headers: { Authorization: `Bearer ${token}` } })
      const usersReq = axios.get('http://127.0.0.1:8000/owners', { headers: { Authorization: `Bearer ${token}` } })

      Promise.all([settingsReq, usersReq])
        .then(([setRes, userRes]) => {
          setSettings(setRes.data)
          setAllUsers(userRes.data)
        })
        .catch(err => console.error(err))
        .finally(() => setLoading(false))
    }
  }, [token, leagueId])

  // 2.3 EFFECT: Trigger load on mount
  useEffect(() => { loadData() }, [loadData])

  // --- HANDLERS ---
  const handleUpdate = (field, value) => { setSettings({ ...settings, [field]: value }); setUnsavedChanges(true); }
  
  const handleRuleChange = (idx, field, val) => { 
    const n = [...settings.scoring_rules]; 
    n[idx][field] = val; 
    setSettings({ ...settings, scoring_rules: n }); 
    setUnsavedChanges(true); 
  }

  const saveSettings = () => {
    axios.put(`http://127.0.0.1:8000/leagues/${leagueId}/settings`, settings, { headers: { Authorization: `Bearer ${token}` } })
      .then(() => { alert("Saved!"); setUnsavedChanges(false); })
      .catch(() => alert("Error saving"))
  }

  const handleCreateOwner = () => {
    if(!newOwnerName) return;
    axios.post(`http://127.0.0.1:8000/leagues/owners`, 
        { username: newOwnerName, email: newOwnerEmail }, 
        { headers: { Authorization: `Bearer ${token}` } }
    )
    .then(() => { 
        alert(`User created!`); 
        setNewOwnerName(''); 
        setNewOwnerEmail(''); 
        loadData(); 
    })
    .catch(err => alert("Error: " + (err.response?.data?.detail || err.message)))
  }

  // --- DATA MAPPING ---
  if (loading) return <div className="text-white text-center mt-20 animate-pulse">Entering The War Room...</div>

  // (Include your existing JSX logic here - it remains largely the same)
  // Ensure that no functions are defined inside the 'activeRules.map' that create components.
  
  return (
    <div className="p-8">
      {/* View Logic (Menu, Scoring, Users) goes here */}
      {view === 'menu' && <h1 className="text-white">Commissioner Dashboard</h1>}
    </div>
  )
}