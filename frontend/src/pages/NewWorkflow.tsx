import { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

export default function NewWorkflow() {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleRun = async () => {
    if (!request.trim()) return;
    setLoading(true);
    try {
      const res = await axios.post('/api/workflows', { request });
      navigate(`/workflow/${res.data.workflow_id}`);
    } catch (e) {
      console.error(e);
      alert('Failed to start workflow');
    } finally {
      setLoading(false);
    }
  };

  const templates = [
    "Research FastAPI, Flask, and Django for building AI backends. Compare their architecture, performance considerations, ecosystem, and suitability for AI applications, then produce a technical recommendation.",
    "Calculate 15% of 2000, add 250, then divide by 5.",
    "Calculate 20% of 500, divide by 0, then add 100."
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto mt-12">
      <h1 className="text-4xl font-bold mb-2">New Workflow</h1>
      <p className="text-gray-400 mb-8">Enter a natural language request. The Planner Agent will decompose it into a specialized workflow.</p>

      <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-2xl mb-8">
        <textarea
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          placeholder="e.g. Research FastAPI, compare it with Flask, and generate a report..."
          className="w-full bg-gray-900 border border-gray-700 rounded-lg p-4 text-white placeholder-gray-500 min-h-[150px] mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex justify-end">
          <button
            onClick={handleRun}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-8 rounded-lg transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            {loading ? <span>Starting...</span> : <span>RUN WORKFLOW</span>}
          </button>
        </div>
      </div>

      <div className="mt-12">
        <h3 className="text-gray-400 font-medium mb-4 uppercase text-sm tracking-wider">Example Templates</h3>
        <div className="grid gap-4">
          {templates.map((t, idx) => (
            <div key={idx} onClick={() => setRequest(t)} className="bg-gray-800/50 hover:bg-gray-800 p-4 rounded-lg cursor-pointer transition border border-gray-800 hover:border-gray-600">
              {t}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
