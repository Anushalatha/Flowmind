import { useEffect, useState } from 'react';
import axios from 'axios';

interface BenchmarkRun {
  run_id: string;
  suite_version: string;
  mode: string;
  start_time: string;
  end_time: string | null;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  skipped_cases: number;
  metrics: Record<string, number>;
}

interface BenchmarkCase {
  case_id: string;
  category: string;
  status: string;
  workflow_id: string | null;
  latency_seconds: number;
  error_message: string | null;
  failure_reason: string | null;
  expected_status: string;
  actual_status: string | null;
  output_correct: boolean | null;
}

export default function BenchmarkResults() {
  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BenchmarkRun | null>(null);
  const [cases, setCases] = useState<BenchmarkCase[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRuns();
    fetchSummary();
  }, []);

  const fetchRuns = async () => {
    try {
      const res = await axios.get('/api/benchmark/runs');
      setRuns(res.data);
    } catch (err) {
      console.error('Failed to fetch benchmark runs:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await axios.get('/api/benchmark/metrics/summary');
      setSummary(res.data);
    } catch (err) {
      console.error('Failed to fetch benchmark summary:', err);
    }
  };

  const fetchCases = async (runId: string) => {
    try {
      const res = await axios.get(`/api/benchmark/runs/${runId}/cases`);
      setCases(res.data);
    } catch (err) {
      console.error('Failed to fetch benchmark cases:', err);
    }
  };

  const selectRun = (run: BenchmarkRun) => {
    setSelectedRun(run);
    fetchCases(run.run_id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'text-green-400 bg-green-900/30 border-green-800';
      case 'failed':
        return 'text-red-400 bg-red-900/30 border-red-800';
      case 'error':
        return 'text-yellow-400 bg-yellow-900/30 border-yellow-800';
      default:
        return 'text-gray-400 bg-gray-900/30 border-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-500">
        Loading benchmark results...
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-gray-950">
      <div className="p-6 border-b border-gray-800 bg-gray-900">
        <h2 className="text-2xl font-bold">Benchmark Results</h2>
        <p className="text-gray-400 text-sm mt-1">FlowMind performance and reliability metrics</p>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar - Run list */}
        <div className="w-80 border-r border-gray-800 bg-gray-900 overflow-y-auto">
          <div className="p-4 border-b border-gray-800">
            <h3 className="font-semibold text-lg">Benchmark Runs</h3>
          </div>
          <div className="p-2 space-y-2">
            {runs.map((run) => (
              <div
                key={run.run_id}
                onClick={() => selectRun(run)}
                className={`p-3 rounded-lg cursor-pointer border transition-colors ${
                  selectedRun?.run_id === run.run_id
                    ? 'bg-blue-900/30 border-blue-800'
                    : 'bg-gray-800 border-gray-700 hover:border-gray-600'
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-mono text-gray-400">{run.run_id.slice(0, 8)}...</span>
                  <span className={`text-xs px-2 py-1 rounded ${
                    run.mode === 'controlled' ? 'bg-purple-900/30 text-purple-400' : 'bg-orange-900/30 text-orange-400'
                  }`}>
                    {run.mode.toUpperCase()}
                  </span>
                </div>
                <div className="text-sm font-medium mb-1">
                  {run.passed_cases}/{run.total_cases} passed
                </div>
                <div className="text-xs text-gray-400">
                  Pass Rate: {run.metrics?.expected_behavior_pass_rate || 0}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-y-auto p-6">
          {summary && (
            <div className="mb-8">
              <h3 className="text-xl font-semibold mb-4">Overall Summary</h3>
              <div className="grid grid-cols-2 gap-4">
                {summary.controlled && (
                  <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                    <h4 className="text-sm font-medium text-purple-400 mb-3">CONTROLLED MODE</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Total Runs:</span>
                        <span>{summary.controlled.total_runs}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Total Cases:</span>
                        <span>{summary.controlled.total_cases}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Pass Rate:</span>
                        <span className="text-green-400">{summary.controlled.average_pass_rate}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Median Latency:</span>
                        <span>{summary.controlled.average_metrics?.median_latency || 0}s</span>
                      </div>
                    </div>
                  </div>
                )}
                {summary.live && (
                  <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                    <h4 className="text-sm font-medium text-orange-400 mb-3">LIVE MODE</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-400">Total Runs:</span>
                        <span>{summary.live.total_runs}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Total Cases:</span>
                        <span>{summary.live.total_cases}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Pass Rate:</span>
                        <span className="text-green-400">{summary.live.average_pass_rate}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-400">Median Latency:</span>
                        <span>{summary.live.average_metrics?.median_latency || 0}s</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {selectedRun && (
            <div>
              <h3 className="text-xl font-semibold mb-4">Run Details</h3>
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
                <div className="grid grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-gray-400 mb-1">Run ID</div>
                    <div className="font-mono">{selectedRun.run_id.slice(0, 12)}...</div>
                  </div>
                  <div>
                    <div className="text-gray-400 mb-1">Mode</div>
                    <div className={selectedRun.mode === 'controlled' ? 'text-purple-400' : 'text-orange-400'}>
                      {selectedRun.mode.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400 mb-1">Pass Rate</div>
                    <div className="text-green-400">{selectedRun.metrics?.expected_behavior_pass_rate || 0}%</div>
                  </div>
                  <div>
                    <div className="text-gray-400 mb-1">Median Latency</div>
                    <div>{selectedRun.metrics?.median_latency || 0}s</div>
                  </div>
                </div>
              </div>

              <h4 className="text-lg font-semibold mb-3">Case Results</h4>
              <div className="space-y-2">
                {cases.map((benchmarkCase) => (
                  <div key={benchmarkCase.case_id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-medium">{benchmarkCase.case_id}</div>
                        <div className="text-sm text-gray-400">{benchmarkCase.category}</div>
                      </div>
                      <span className={`px-3 py-1 rounded-full text-sm border ${getStatusColor(benchmarkCase.status)}`}>
                        {benchmarkCase.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm mt-3">
                      <div>
                        <div className="text-gray-400">Expected Status</div>
                        <div>{benchmarkCase.expected_status}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Actual Status</div>
                        <div>{benchmarkCase.actual_status || 'N/A'}</div>
                      </div>
                      <div>
                        <div className="text-gray-400">Latency</div>
                        <div>{benchmarkCase.latency_seconds.toFixed(3)}s</div>
                      </div>
                    </div>
                    {benchmarkCase.failure_reason && (
                      <div className="mt-2 text-sm text-red-400">
                        Failure: {benchmarkCase.failure_reason}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!selectedRun && (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Select a benchmark run to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
