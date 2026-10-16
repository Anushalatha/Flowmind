import { useEffect, useState } from 'react';
import axios from 'axios';

export default function Monitoring() {
  const [metrics, setMetrics] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios.get('/api/metrics').then((res) => {
      setMetrics(res.data);
    }).catch(err => {
      console.error(err);
      setError("Failed to load metrics");
    });
  }, []);

  if (error) return <div className="p-8 text-red-400">{error}</div>;
  if (!metrics) return <div className="p-8 text-gray-400">Loading observability data...</div>;

  const toolUsageKeys = Object.keys(metrics.tool_usage);
  const agentUsageKeys = Object.keys(metrics.agent_usage);

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">System Observability</h1>
      
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Total Workflows</div>
          <div className="text-2xl font-semibold">{metrics.total_workflows}</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Success Rate</div>
          <div className="text-2xl font-semibold text-green-400">{metrics.success_rate.toFixed(1)}%</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Avg Latency</div>
          <div className="text-2xl font-semibold text-blue-400">{metrics.average_latency.toFixed(1)}s</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Retry Rate</div>
          <div className="text-2xl font-semibold text-yellow-400">{metrics.retry_rate.toFixed(1)}%</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-8 mb-8">
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Tool Usage</h3>
          <div className="space-y-4">
            {toolUsageKeys.length > 0 ? toolUsageKeys.map(tool => (
              <div key={tool} className="flex justify-between items-center bg-gray-900 p-3 rounded">
                <span>{tool}</span>
                <span className="font-mono text-gray-400">{metrics.tool_usage[tool]} calls</span>
              </div>
            )) : <div className="text-gray-500">No tools have been used yet.</div>}
          </div>
        </div>
        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
          <h3 className="text-lg font-medium mb-4">Agent Usage</h3>
          <div className="space-y-4">
            {agentUsageKeys.length > 0 ? agentUsageKeys.map(agent => (
              <div key={agent} className="flex justify-between items-center bg-gray-900 p-3 rounded">
                <span>{agent}</span>
                <span className="font-mono text-gray-400">{metrics.agent_usage[agent]} invocations</span>
              </div>
            )) : <div className="text-gray-500">No agents have been used yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
