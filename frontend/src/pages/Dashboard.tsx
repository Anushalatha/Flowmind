import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

type Workflow = {
  workflow_id: string;
  status: string;
  user_request: string;
};

type Metrics = {
  total_workflows: number;
  success_rate: number;
  average_latency: number;
  failed_workflows: number;
};

export default function Dashboard() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<'recent' | 'failed'>('recent');
  const [refreshKey, setRefreshKey] = useState(0);
  const [busyWorkflow, setBusyWorkflow] = useState<string | null>(null);
  const [editingWorkflow, setEditingWorkflow] = useState<Workflow | null>(null);
  const [editedRequest, setEditedRequest] = useState('');

  useEffect(() => {
    let cancelled = false;
    const workflowParams = statusFilter === 'failed'
      ? { status: 'failed', limit: 200 }
      : { limit: 50 };

    Promise.all([
      axios.get<Workflow[]>('/api/workflows', { params: workflowParams }),
      axios.get<Metrics>('/api/metrics'),
    ]).then(([workflowResponse, metricsResponse]) => {
      if (!cancelled) {
        setWorkflows(workflowResponse.data);
        setMetrics(metricsResponse.data);
      }
    }).catch((err: unknown) => {
      console.error(err);
      if (!cancelled) setError('Failed to load dashboard data');
    });

    return () => {
      cancelled = true;
    };
  }, [statusFilter, refreshKey]);

  async function rerunWorkflow(workflow: Workflow, request?: string) {
    setBusyWorkflow(workflow.workflow_id);
    setActionError(null);
    setActionMessage(null);
    try {
      const response = await axios.post<{ workflow_id: string }>(
        `/api/workflows/${workflow.workflow_id}/rerun`,
        request === undefined ? {} : { request },
      );
      setEditingWorkflow(null);
      setStatusFilter('recent');
      setRefreshKey((key) => key + 1);
      setActionMessage(`New workflow started (${response.data.workflow_id.slice(0, 8)}).`);
    } catch (err: unknown) {
      console.error(err);
      setActionError('Failed to start the workflow. Please try again.');
    } finally {
      setBusyWorkflow(null);
    }
  }

  async function deleteWorkflow(workflow: Workflow) {
    if (!window.confirm(`Permanently delete workflow ${workflow.workflow_id.slice(0, 8)} and its event history?`)) {
      return;
    }
    setBusyWorkflow(workflow.workflow_id);
    setActionError(null);
    setActionMessage(null);
    try {
      await axios.delete(`/api/workflows/${workflow.workflow_id}`);
      setRefreshKey((key) => key + 1);
      setActionMessage('Workflow and its event history were deleted.');
    } catch (err: unknown) {
      console.error(err);
      setActionError('Failed to delete workflow. Active workflows cannot be deleted.');
    } finally {
      setBusyWorkflow(null);
    }
  }

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

      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">
          {statusFilter === 'failed' ? `Failed Workflows (${metrics.failed_workflows})` : 'Recent Executions'}
        </h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setStatusFilter('recent')}
            aria-pressed={statusFilter === 'recent'}
            className={`rounded-lg px-3 py-2 text-sm ${statusFilter === 'recent' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}`}
          >
            Recent
          </button>
          <button
            type="button"
            onClick={() => setStatusFilter('failed')}
            aria-pressed={statusFilter === 'failed'}
            className={`rounded-lg px-3 py-2 text-sm ${statusFilter === 'failed' ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'}`}
          >
            Failed ({metrics.failed_workflows})
          </button>
        </div>
      </div>
      {actionError && <div role="alert" className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-red-300">{actionError}</div>}
      {actionMessage && <div role="status" className="mb-4 rounded-lg border border-green-500/30 bg-green-500/10 p-3 text-green-300">{actionMessage}</div>}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full min-w-[900px] text-left">
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
                  <div className="flex flex-wrap items-center gap-3">
                    <Link to={`/workflow/${wf.workflow_id}`} className="text-blue-400 hover:text-blue-300">View</Link>
                    {wf.status === 'failed' && (
                      <button
                        type="button"
                        disabled={busyWorkflow === wf.workflow_id}
                        onClick={() => rerunWorkflow(wf)}
                        className="text-green-400 hover:text-green-300 disabled:opacity-50"
                      >
                        Retry
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={busyWorkflow === wf.workflow_id}
                      onClick={() => {
                        setEditingWorkflow(wf);
                        setEditedRequest(wf.user_request);
                        setActionError(null);
                        setActionMessage(null);
                      }}
                      className="text-gray-300 hover:text-white disabled:opacity-50"
                    >
                      Edit &amp; rerun
                    </button>
                    <button
                      type="button"
                      disabled={busyWorkflow === wf.workflow_id}
                      onClick={() => deleteWorkflow(wf)}
                      className="text-red-400 hover:text-red-300 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {workflows.length === 0 && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-gray-500">
                  {statusFilter === 'failed' ? 'No failed workflows found.' : 'No workflows found. Run one to get started!'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editingWorkflow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void rerunWorkflow(editingWorkflow, editedRequest);
            }}
            className="w-full max-w-2xl rounded-xl border border-gray-700 bg-gray-800 p-6 shadow-xl"
          >
            <h2 className="mb-2 text-xl font-semibold">Edit workflow request</h2>
            <p className="mb-4 text-sm text-gray-400">
              This starts a new workflow. The existing workflow and its history will not be changed.
            </p>
            <textarea
              autoFocus
              required
              value={editedRequest}
              onChange={(event) => setEditedRequest(event.target.value)}
              rows={5}
              className="mb-4 w-full rounded-lg border border-gray-600 bg-gray-900 p-3 text-gray-100 focus:border-blue-500 focus:outline-none"
              aria-label="Workflow request"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setEditingWorkflow(null)}
                className="rounded-lg px-4 py-2 text-gray-300 hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!editedRequest.trim() || busyWorkflow === editingWorkflow.workflow_id}
                className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
              >
                Save &amp; rerun
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
