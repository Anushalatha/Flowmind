import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

export default function Dashboard() {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios.get('/api/workflows').then((res) => {
      setWorkflows(res.data);
    }).catch(console.error);

    axios.get('/api/metrics').then((res) => {
      setMetrics(res.data);
    }).catch(err => {
      console.error(err);
      setError("Failed to load metrics");
    });
  }, []);

  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!metrics) return <div className="p-8 text-gray-400">Loading dashboard...</div>;

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>
      
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Total Workflows</div>
          <div className="text-3xl font-semibold">{metrics.total_workflows}</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Success Rate</div>
          <div className="text-3xl font-semibold text-green-400">{metrics.success_rate.toFixed(1)}%</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Avg Latency</div>
          <div className="text-3xl font-semibold text-blue-400">{metrics.average_latency.toFixed(1)}s</div>
        </div>
      </div>

      <h2 className="text-xl font-semibold mb-4">Recent Executions</h2>
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="p-4 font-medium text-gray-400">ID</th>
              <th className="p-4 font-medium text-gray-400">Request</th>
              <th className="p-4 font-medium text-gray-400">Status</th>
              <th className="p-4 font-medium text-gray-400">Action</th>
            </tr>
          </thead>
          <tbody>
            {workflows.map(wf => (
              <tr key={wf.workflow_id} className="border-b border-gray-800 last:border-0 hover:bg-gray-750">
                <td className="p-4 font-mono text-sm text-gray-300">{wf.workflow_id.slice(0, 8)}</td>
                <td className="p-4 truncate max-w-md">{wf.user_request}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded-full text-xs ${wf.status === 'completed' ? 'bg-green-500/20 text-green-300' : wf.status === 'failed' ? 'bg-red-500/20 text-red-300' : 'bg-blue-500/20 text-blue-300'}`}>
                    {wf.status.toUpperCase()}
                  </span>
                </td>
                <td className="p-4">
                  <Link to={`/workflow/${wf.workflow_id}`} className="text-blue-400 hover:text-blue-300">View</Link>
                </td>
              </tr>
            ))}
            {workflows.length === 0 && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-gray-500">No workflows found. Run one to get started!</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
