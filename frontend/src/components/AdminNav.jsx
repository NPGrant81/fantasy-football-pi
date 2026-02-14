// frontend/src/components/AdminNav.jsx
export default function AdminNav() {
  return (
    <nav className="bg-purple-900/20 p-4 border-b border-purple-500/30 flex gap-6">
      <div className="font-black text-purple-400 uppercase tracking-tighter">Site Admin</div>
      <a href="/admin/leagues" className="hover:text-white text-slate-400 transition">Manage Leagues</a>
      <a href="/admin/users" className="hover:text-white text-slate-400 transition">Global Users</a>
      <a href="/admin/sandbox" className="text-green-400 hover:text-green-300 transition">+ Create Sandbox</a>
    </nav>
  );
}
