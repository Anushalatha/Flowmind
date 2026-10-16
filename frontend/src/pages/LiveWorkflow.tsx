import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import ReactFlow, { Background, Controls, MarkerType, useReactFlow, ReactFlowProvider } from 'reactflow';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import 'reactflow/dist/style.css';

function LiveWorkflowContent() {
  const { id } = useParams();
  const { fitView } = useReactFlow();
  const [workflow, setWorkflow] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, string>>({});
  const nodeStatusesRef = useRef(nodeStatuses);

  // Keep ref in sync with state
  useEffect(() => {
    nodeStatusesRef.current = nodeStatuses;
  }, [nodeStatuses]);

  const getNodeStyle = (status: string) => {
    const baseStyle = {
      backgroundColor: '#1e293b', // bg-gray-800
      color: '#fff',
      border: '1px solid #334155', // border-gray-700
      borderRadius: '8px',
      padding: '12px',
      minWidth: '200px',
      maxWidth: '280px',
      whiteSpace: 'pre-wrap' as const,
      textAlign: 'left' as const,
    };

    switch (status) {
      case 'planning':
        return { ...baseStyle, backgroundColor: '#1e3a8a', borderColor: '#3b82f6' }; // blue
      case 'started':
      case 'running':
        return { ...baseStyle, backgroundColor: '#1e3a8a', borderColor: '#3b82f6' }; // blue
      case 'completed':
        return { ...baseStyle, backgroundColor: '#064e3b', borderColor: '#10b981' }; // green
      case 'failed':
        return { ...baseStyle, backgroundColor: '#7f1d1d', borderColor: '#ef4444' }; // red
      case 'dependency_blocked':
        return { ...baseStyle, backgroundColor: '#7f1d1d', borderColor: '#991b1b', opacity: 0.6 }; // muted red
      case 'empty_result':
        return { ...baseStyle, backgroundColor: '#78350f', borderColor: '#f59e0b' }; // amber/warning
      case 'retrying':
        return { ...baseStyle, backgroundColor: '#78350f', borderColor: '#f59e0b' }; // amber
      case 'pending':
        return { ...baseStyle, backgroundColor: '#1e293b', borderColor: '#475569' }; // gray
      default:
        return baseStyle;
    }
  };

  const updateNodeStatus = (nodeId: string, status: string) => {
    setNodeStatuses(prev => ({ ...prev, [nodeId]: status }));
    setNodes(nds => nds.map(n => {
      if (n.id === nodeId) {
        return { ...n, status };
      }
      return n;
    }));
  };

  const updateGraph = (steps: any[], workflowStatus: string) => {
    console.log('[FlowMind] updateGraph called with steps:', steps, 'status:', workflowStatus);
    const newNodes: any[] = [];
    const newEdges: any[] = [];
    const currentStatuses = nodeStatusesRef.current;

    // Add Planner node
    newNodes.push({
      id: 'planner',
      position: { x: 400, y: 50 },
      data: { label: 'Planner' },
      style: getNodeStyle(currentStatuses['planner'] || (workflowStatus === 'planning' ? 'planning' : 'pending')),
      status: currentStatuses['planner'] || (workflowStatus === 'planning' ? 'planning' : 'pending')
    });

    // Add step nodes with simple grid layout (more reliable than dependency depth calculation)
    steps.forEach((step, idx) => {
      const status = currentStatuses[step.step_id] || 'pending';
      const x = 100 + (idx % 3) * 300;
      const y = 200 + Math.floor(idx / 3) * 150;
      // Create meaningful label from action and tool - action is the primary label, tool is secondary
      const label = step.action;
      const toolLabel = step.tool_name ? `(${step.tool_name})` : '';
      const fullLabel = toolLabel ? `${label}\n${toolLabel}` : label;
      newNodes.push({
        id: step.step_id,
        position: { x, y },
        data: { label: fullLabel },
        style: getNodeStyle(status),
        status
      });
    });

    // Add Synthesis node
    newNodes.push({
      id: 'synthesis',
      position: { x: 400, y: 200 + Math.ceil(steps.length / 3) * 150 + 50 },
      data: { label: 'Synthesis' },
      style: getNodeStyle(currentStatuses['synthesis'] || (workflowStatus === 'completed' ? 'completed' : 'pending')),
      status: currentStatuses['synthesis'] || (workflowStatus === 'completed' ? 'completed' : 'pending')
    });

    // Add edges from dependencies
    if (steps.length > 0) {
      // Edge from planner to steps with no dependencies (first level steps)
      steps.forEach(step => {
        if (step.depends_on.length === 0) {
          newEdges.push({
            id: `e-planner-${step.step_id}`,
            source: 'planner',
            target: step.step_id,
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
            style: { stroke: '#94a3b8' }
          });
        }
      });

      // Edges between steps based on dependencies
      steps.forEach(step => {
        step.depends_on.forEach((dep: string) => {
          newEdges.push({
            id: `e-${dep}-${step.step_id}`,
            source: dep,
            target: step.step_id,
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
            style: { stroke: '#94a3b8' }
          });
        });
      });

      // Edge from all leaf steps (steps that no other step depends on) to synthesis
      const stepIds = new Set(steps.map(s => s.step_id));
      const deps = new Set(steps.flatMap(s => s.depends_on));
      const leafSteps = [...stepIds].filter(id => !deps.has(id));

      leafSteps.forEach(stepId => {
        newEdges.push({
          id: `e-${stepId}-synthesis`,
          source: stepId,
          target: 'synthesis',
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
          style: { stroke: '#94a3b8' }
        });
      });
    } else {
      // Edge from planner to synthesis if no steps
      newEdges.push({
        id: 'e-planner-synthesis',
        source: 'planner',
        target: 'synthesis',
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
        style: { stroke: '#94a3b8' }
      });
    }

    console.log('[FlowMind] Setting nodes:', newNodes);
    console.log('[FlowMind] Setting edges:', newEdges);
    setNodes(newNodes);
    setEdges(newEdges);

    // Fit view after nodes are updated
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 800 });
    }, 100);
  };

  useEffect(() => {
    // Fetch initial state
    axios.get(`/api/workflows/${id}`).then(res => {
      console.log('[FlowMind] Fetched workflow state:', res.data);
      setWorkflow(res.data);
      // Reconstruct graph from persisted data
      if (res.data.plan && res.data.plan.steps) {
        console.log('[FlowMind] Reconstructing graph from persisted plan:', res.data.plan.steps);
        updateGraph(res.data.plan.steps, res.data.status);
      } else if (res.data.status) {
        // Show initial state even without plan
        console.log('[FlowMind] No plan found, showing initial state');
        updateGraph([], res.data.status);
      }
    }).catch(err => {
      console.error('Failed to fetch workflow:', err);
    });

    // Setup SSE
    const evtSource = new EventSource(`/api/workflows/${id}/stream`);
    evtSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('[FlowMind] SSE event:', data);
      setEvents(prev => [...prev, data]);

      // Handle workflow lifecycle events
      if (data.event_type === 'workflow.started') {
        setWorkflow((prev: any) => ({ ...prev, status: 'running' }));
        updateGraph([], 'running');
      }
      if (data.event_type === 'planner.started') {
        setWorkflow((prev: any) => ({ ...prev, status: 'planning' }));
        updateNodeStatus('planner', 'planning');
      }
      if (data.event_type === 'planner.completed') {
        console.log('[FlowMind] Planner completed, metadata:', data.metadata);
        if (data.metadata?.plan) {
          console.log('[FlowMind] Creating graph from planner plan:', data.metadata.plan.steps);
          setWorkflow((prev: any) => ({ ...prev, plan: data.metadata.plan, status: 'running' }));
          updateGraph(data.metadata.plan.steps, 'running');
          updateNodeStatus('planner', 'completed');
        } else {
          // Fallback: try to fetch workflow state again
          console.log('[FlowMind] No plan in planner.completed metadata, fetching from API');
          axios.get(`/api/workflows/${id}`).then(res => {
            console.log('[FlowMind] Fetched workflow state:', res.data);
            if (res.data.plan && res.data.plan.steps) {
              setWorkflow((prev: any) => ({ ...prev, plan: res.data.plan, status: 'running' }));
              updateGraph(res.data.plan.steps, 'running');
              updateNodeStatus('planner', 'completed');
            }
          });
        }
      }
      if (data.event_type === 'workflow.completed' && data.metadata?.final_response) {
        setWorkflow((prev: any) => ({ ...prev, status: data.status, final_response: data.metadata.final_response }));
        updateNodeStatus('synthesis', 'completed');
      }
      if (data.event_type === 'workflow.failed') {
        setWorkflow((prev: any) => ({ ...prev, status: 'failed' }));
      }

      // Handle step events
      if (data.step_id) {
        updateNodeStatus(data.step_id, data.status);
        // Also update node style immediately
        setNodes(nds => {
          console.log('[FlowMind] Updating node status for', data.step_id, 'to', data.status, 'current nodes:', nds);
          return nds.map(n => {
            if (n.id === data.step_id) {
              return { ...n, style: getNodeStyle(data.status), status: data.status };
            }
            return n;
          });
        });
      }

      // Handle retry events
      if (data.event_type === 'retry.started' && data.step_id) {
        updateNodeStatus(data.step_id, 'retrying');
        setNodes(nds => nds.map(n => {
          if (n.id === data.step_id) {
            return { ...n, style: getNodeStyle('retrying'), status: 'retrying' };
          }
          return n;
        }));
      }
    };
    return () => evtSource.close();
  }, [id]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <div className="p-6 border-b border-gray-800 bg-gray-900 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Live Execution</h2>
          <p className="text-gray-400 font-mono text-sm mt-1">{id}</p>
        </div>
        <div className={`px-4 py-2 rounded-full font-medium border ${
          workflow?.status === 'completed' ? 'bg-green-900/30 text-green-400 border-green-800' :
          workflow?.status === 'failed' ? 'bg-red-900/30 text-red-400 border-red-800' :
          workflow?.status === 'partially_completed' ? 'bg-yellow-900/30 text-yellow-400 border-yellow-800' :
          'bg-blue-900/30 text-blue-400 border-blue-800'
        }`}>
          {workflow?.status?.toUpperCase().replace('_', ' ') || 'LOADING'}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Main Graph Area */}
        <div className="flex-1 relative bg-gray-950">
          {nodes.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <p className="text-lg mb-2">No workflow graph available</p>
                <p className="text-sm">Waiting for planning to complete...</p>
              </div>
            </div>
          ) : (
            <ReactFlow nodes={nodes} edges={edges}>
              <Background color="#334155" size={1} />
              <Controls />
            </ReactFlow>
          )}
        </div>

        {/* Sidebar panels */}
        <div className="w-96 bg-gray-900 border-l border-gray-800 flex flex-col">
          <div className="p-4 border-b border-gray-800 bg-gray-950">
            <h3 className="font-semibold text-lg">Execution Timeline</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs">
            {events.map((ev, i) => (
              <div key={i} className="border-l-2 border-gray-700 pl-4 py-1">
                <div className="text-gray-500 mb-1">{new Date(ev.timestamp).toLocaleTimeString()}</div>
                <div className="text-gray-300 font-semibold">{ev.event_type}</div>
                {ev.step_id && <div className="text-blue-400 mt-1">Step: {ev.step_id}</div>}
                {ev.status === 'failed' && <div className="text-red-400 mt-1">{ev.metadata?.error}</div>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Result Panel */}
      {workflow?.final_response && (
        <div className="h-64 bg-gray-900 border-t border-gray-800 p-6 overflow-y-auto">
          <h3 className="text-xl font-semibold mb-4 text-green-400">Final Synthesis</h3>
          <div className="markdown-content text-gray-100 text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({children}) => <h1 className="text-2xl font-bold text-white mb-4 mt-6">{children}</h1>,
                h2: ({children}) => <h2 className="text-xl font-bold text-white mb-3 mt-5">{children}</h2>,
                h3: ({children}) => <h3 className="text-lg font-semibold text-white mb-2 mt-4">{children}</h3>,
                h4: ({children}) => <h4 className="text-base font-semibold text-gray-200 mb-2 mt-3">{children}</h4>,
                p: ({children}) => <p className="mb-3">{children}</p>,
                strong: ({children}) => <strong className="font-bold text-white">{children}</strong>,
                em: ({children}) => <em className="italic text-gray-300">{children}</em>,
                ul: ({children}) => <ul className="list-disc list-inside mb-4 space-y-1">{children}</ul>,
                ol: ({children}) => <ol className="list-decimal list-inside mb-4 space-y-1">{children}</ol>,
                li: ({children}) => <li className="text-gray-200">{children}</li>,
                code: ({node, className, children, ...props}) => {
                  // Check if code is inline (not inside a pre tag)
                  const hasLanguageClass = className && /language-/.test(className);
                  if (!hasLanguageClass) {
                    return <code className="bg-gray-800 text-blue-300 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>;
                  }
                  return <code className={className} {...props}>{children}</code>;
                },
                pre: ({children}) => <pre className="bg-gray-800 p-4 rounded-lg overflow-x-auto mb-4 border border-gray-700">{children}</pre>,
                a: ({href, children}) => <a href={href} className="text-blue-400 hover:text-blue-300 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                blockquote: ({children}) => <blockquote className="border-l-4 border-gray-600 pl-4 italic text-gray-300 mb-4">{children}</blockquote>,
                hr: () => <hr className="border-gray-700 my-4" />,
                table: ({children}) => (
                  <div className="overflow-x-auto mb-4">
                    <table className="min-w-full border border-gray-700 rounded-lg overflow-hidden">{children}</table>
                  </div>
                ),
                thead: ({children}) => <thead className="bg-gray-800">{children}</thead>,
                tbody: ({children}) => <tbody className="divide-y divide-gray-700">{children}</tbody>,
                tr: ({children}) => <tr className="hover:bg-gray-800/50">{children}</tr>,
                th: ({children}) => <th className="px-4 py-2 text-left text-sm font-semibold text-white border-b border-gray-700">{children}</th>,
                td: ({children}) => <td className="px-4 py-2 text-sm text-gray-200 border-b border-gray-700">{children}</td>,
              }}
            >
              {workflow.final_response}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LiveWorkflow() {
  return (
    <ReactFlowProvider>
      <LiveWorkflowContent />
    </ReactFlowProvider>
  );
}
