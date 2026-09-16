export default function Home() {
  return (
    <main className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      <div className="text-center">
        <h1 className="text-5xl font-bold text-white mb-4">EPIRO</h1>
        <p className="text-xl text-slate-300 mb-8">
          Evidence • Public Information • Engagement • Intelligence • Readiness
        </p>
        <p className="text-lg text-slate-400 mb-8">
          Operational Intelligence and Evidence Management Platform
        </p>
        <div className="space-x-4">
          <a href="/dashboard" className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Dashboard
          </a>
          <a href="/login" className="inline-block px-6 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600">
            Login
          </a>
        </div>
      </div>
    </main>
  )
}
