import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import NewWorkflow from './pages/NewWorkflow';
import LiveWorkflow from './pages/LiveWorkflow';
import Monitoring from './pages/Monitoring';
import BenchmarkResults from './pages/BenchmarkResults';
import { LayoutDashboard, Play, Activity, BarChart3 } from 'lucide-react';
import { ReactFlowProvider } from 'reactflow';
import 'reactflow/dist/style.css';

function Sidebar() {
  return (
    <div className="w-64 bg-gray-950 h-screen border-r border-gray-800 p-4 flex flex-col">
      <div className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500 mb-8">
        FLOWMIND
      </div>
      <nav className="flex-1 space-y-2">
        <Link to="/" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-800 transition-colors">
          <LayoutDashboard size={20} className="text-gray-400" />
          <span>Dashboard</span>
        </Link>
        <Link to="/new" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-800 transition-colors">
          <Play size={20} className="text-gray-400" />
          <span>New Workflow</span>
        </Link>
        <Link to="/monitoring" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-800 transition-colors">
          <Activity size={20} className="text-gray-400" />
          <span>Monitoring</span>
        </Link>
        <Link to="/benchmarks" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-800 transition-colors">
          <BarChart3 size={20} className="text-gray-400" />
          <span>Benchmarks</span>
        </Link>
      </nav>
    </div>
  );
}

function App() {
  return (
    <ReactFlowProvider>
      <BrowserRouter>
        <div className="flex h-screen overflow-hidden bg-gray-900 text-gray-100">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/new" element={<NewWorkflow />} />
              <Route path="/workflow/:id" element={<LiveWorkflow />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/benchmarks" element={<BenchmarkResults />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ReactFlowProvider>
  );
}

export default App;
