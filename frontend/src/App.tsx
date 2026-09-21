import { useState, useEffect, useRef } from 'react';
import { 
  BarChart3, RefreshCw, Send, Zap, ShieldAlert,
  Sparkles, ChevronDown, ChevronUp, MessageSquare, LayoutDashboard,
  Plus, PanelLeft, Shield, AlertTriangle
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer 
} from 'recharts';

const API_BASE = 'http://127.0.0.1:8000';

interface SummaryMetrics {
  total_requests: number;
  overall_hit_rate: number;
  hits: number;
  misses: number;
  blocked_by_guard: number;
  avg_latency_ms: number;
  median_latency_ms: number;
  p95_latency_ms: number;
  total_cost_usd: number;
  estimated_cost_saved_usd: number;
  requests_by_provider: Record<string, number>;
  requests_by_tier: Record<string, number>;
}

interface TimeseriesPoint {
  timestamp: string;
  requests: number;
  hit_rate: number;
  avg_latency_ms: number;
  cost_usd: number;
}

interface RequestRecord {
  id: number;
  timestamp: string;
  prompt: string;
  cache_outcome: 'hit' | 'miss' | 'blocked_by_guard';
  similarity_score?: number;
  threshold_used: number;
  risk_score: number;
  provider: string;
  model: string;
  tier: string;
  latency_ms: number;
  estimated_cost_usd: number;
  guard_reason?: string;
}

interface EvalModeResult {
  mode: string;
  total_pairs: number;
  TP: number;
  FP: number;
  TN: number;
  FN: number;
  precision: number;
  recall: number;
  fpr: number;
  fnr: number;
  overall_hit_rate: number;
  recall_low_risk_a1: number;
  recall_high_risk_a2: number;
  avg_latency_ms: number;
  median_latency_ms: number;
}

interface ChatTurn {
  id: string;
  timestamp: string;
  prompt: string;
  mode: string;
  responsePayload: any;
  showDetails?: boolean;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'dashboard' | 'evaluation'>('chat');
  const [window, setWindow] = useState<'1h' | '24h' | '7d'>('1h');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  // Data state
  const [summary, setSummary] = useState<SummaryMetrics | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [recent, setRecent] = useState<RequestRecord[]>([]);
  const [evalResults, setEvalResults] = useState<Record<string, EvalModeResult> | null>(null);
  
  // Interactive Chat State
  const [consoleInput, setConsoleInput] = useState('');
  const [consoleMode, setConsoleMode] = useState<'hybrid' | 'adaptive' | 'fixed' | 'disabled'>('hybrid');
  const [submitting, setSubmitting] = useState(false);
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);

  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Fetch telemetry from gateway metrics API
  const fetchTelemetry = async () => {
    try {
      const [sumRes, timeRes, recRes, evalRes] = await Promise.all([
        fetch(`${API_BASE}/api/metrics/summary`),
        fetch(`${API_BASE}/api/metrics/timeseries?window=${window}`),
        fetch(`${API_BASE}/api/metrics/recent?limit=50`),
        fetch(`${API_BASE}/api/metrics/eval-results`)
      ]);

      if (sumRes.ok) setSummary(await sumRes.json());
      if (timeRes.ok) setTimeseries(await timeRes.json());
      if (recRes.ok) setRecent(await recRes.json());
      if (evalRes.ok) setEvalResults(await evalRes.json());
    } catch (err) {
      console.error('Failed to fetch gateway metrics:', err);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 5000);
    return () => clearInterval(interval);
  }, [window]);

  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatTurns, submitting]);

  const handleSendPrompt = async (overridePrompt?: string) => {
    const promptToSend = overridePrompt || consoleInput;
    if (!promptToSend.trim() || submitting) return;

    setSubmitting(true);
    if (!overridePrompt) setConsoleInput('');

    const turnId = Date.now().toString();

    try {
      const response = await fetch(`${API_BASE}/v1/chat/completions?cache_mode=${consoleMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptToSend })
      });

      if (!response.ok) {
        throw new Error(`Gateway returned status ${response.status}`);
      }

      const data = await response.json();

      setChatTurns(prev => [
        ...prev,
        {
          id: turnId,
          timestamp: new Date().toLocaleTimeString(),
          prompt: promptToSend,
          mode: consoleMode,
          responsePayload: data,
          showDetails: false
        }
      ]);

      fetchTelemetry();
    } catch (err: any) {
      setChatTurns(prev => [
        ...prev,
        {
          id: turnId,
          timestamp: new Date().toLocaleTimeString(),
          prompt: promptToSend,
          mode: consoleMode,
          responsePayload: {
            response: `Error connecting to gateway: ${err.message}`,
            source: 'error',
            latency: 0,
            cache_lookup_latency_seconds: 0,
            risk_assessment: { risk_score: 0, matched_signals: [], effective_threshold: 0 },
            routing_decision: { provider: 'N/A', model: 'N/A', tier: 'N/A', reasoning: 'Gateway unreachable' },
            estimated_cost_usd: 0,
            similarity_score: null
          },
          showDetails: true
        }
      ]);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleTurnDetails = (turnId: string) => {
    setChatTurns(prev =>
      prev.map(turn =>
        turn.id === turnId ? { ...turn, showDetails: !turn.showDetails } : turn
      )
    );
  };

  const handleNewChat = () => {
    setChatTurns([]);
    setConsoleInput('');
  };

  const suggestions = [
    {
      category: 'Try a paraphrase',
      subtitle: 'Triggers cache hit when semantically equivalent',
      prompt: 'What is the capital of India?'
    },
    {
      category: 'Try a risky action',
      subtitle: 'Routes to capable 120B model (high-risk verb)',
      prompt: 'Cancel my subscription and refund my account balance'
    },
    {
      category: 'Try a trick question',
      subtitle: 'NegationGuard catches opposite intent',
      prompt: 'Do NOT revoke my API access keys immediately'
    }
  ];

  return (
    <div className="flex h-screen bg-zinc-900 text-zinc-100 font-sans antialiased overflow-hidden">
      {/* ---------------------------------------------------------------- border-r border-zinc-800/80 ---------------- */}
      {/* Left Sidebar (ChatGPT layout ~260px wide) */}
      {/* ---------------------------------------------------------------- ---------------- */}
      <aside className={`bg-zinc-950 flex flex-col transition-all duration-300 border-r border-zinc-800/60 z-20 ${sidebarOpen ? 'w-64' : 'w-0 -ml-64'} md:relative fixed inset-y-0 left-0`}>
        <div className="p-3 flex items-center justify-between border-b border-zinc-800/50">
          <div className="flex items-center gap-2.5 px-2 py-1">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <Shield className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <span className="font-semibold text-sm tracking-tight text-zinc-100">SentinelCache</span>
              <span className="text-[10px] block text-emerald-400 font-mono leading-none">v0.5.0 Gateway</span>
            </div>
          </div>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors"
            title="Collapse Sidebar"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-zinc-900 hover:bg-zinc-800/80 text-zinc-100 text-sm font-medium border border-zinc-800 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4 text-emerald-400" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 px-3 space-y-1 py-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left ${
              activeTab === 'chat'
                ? 'bg-zinc-800/90 text-zinc-100 font-medium shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/80'
            }`}
          >
            <MessageSquare className={`w-4 h-4 ${activeTab === 'chat' ? 'text-emerald-400' : ''}`} />
            <span>Chat Console</span>
          </button>

          <button
            onClick={() => setActiveTab('dashboard')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left ${
              activeTab === 'dashboard'
                ? 'bg-zinc-800/90 text-zinc-100 font-medium shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/80'
            }`}
          >
            <LayoutDashboard className={`w-4 h-4 ${activeTab === 'dashboard' ? 'text-emerald-400' : ''}`} />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('evaluation')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left ${
              activeTab === 'evaluation'
                ? 'bg-zinc-800/90 text-zinc-100 font-medium shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/80'
            }`}
          >
            <BarChart3 className={`w-4 h-4 ${activeTab === 'evaluation' ? 'text-emerald-400' : ''}`} />
            <span>Evaluation</span>
          </button>
        </nav>

        {/* System Telemetry Quick Stats Footer */}
        <div className="p-3 border-t border-zinc-800/60 bg-zinc-950/80">
          <div className="bg-zinc-900/70 border border-zinc-800/60 rounded-lg p-2.5 space-y-1.5 text-xs font-mono">
            <div className="flex justify-between text-zinc-400">
              <span>Overall Hit Rate</span>
              <span className="text-emerald-400 font-semibold">{((summary?.overall_hit_rate || 0) * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>Cost Saved</span>
              <span className="text-emerald-400">${(summary?.estimated_cost_saved_usd || 0).toFixed(4)}</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ---------------------------------------------------------------- ---------------- */}
      {/* Main Content Area */}
      {/* ---------------------------------------------------------------- ---------------- */}
      <main className="flex-1 flex flex-col h-full bg-zinc-900 relative overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-14 border-b border-zinc-800/60 flex items-center px-4 justify-between bg-zinc-900/80 backdrop-blur-sm sticky top-0 z-10">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button 
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                title="Expand Sidebar"
              >
                <PanelLeft className="w-5 h-5" />
              </button>
            )}
            <h1 className="text-base font-semibold text-zinc-100">
              {activeTab === 'chat' && 'Chat Console'}
              {activeTab === 'dashboard' && 'Observability Dashboard'}
              {activeTab === 'evaluation' && 'Evaluation Benchmark Matrix'}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs font-mono text-zinc-400 bg-zinc-800/60 px-2.5 py-1 rounded-full border border-zinc-700/50">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Gateway Online
            </span>
          </div>
        </header>

        {/* ---------------------------------------------------------------- ---------------- */}
        {/* TAB 1: CHAT CONSOLE */}
        {/* ---------------------------------------------------------------- ---------------- */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden">
            {/* Scrollable Chat Area */}
            <div className="flex-1 overflow-y-auto px-4 py-6">
              <div className="max-w-3xl mx-auto space-y-6">
                
                {/* Empty State */}
                {chatTurns.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center space-y-6">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-emerald-700/10 border border-emerald-500/30 flex items-center justify-center shadow-lg shadow-emerald-950/30">
                      <Shield className="w-7 h-7 text-emerald-400" />
                    </div>
                    
                    <div className="space-y-2 max-w-md">
                      <h2 className="text-2xl font-bold text-zinc-100 tracking-tight">SentinelCache Gateway</h2>
                      <p className="text-sm text-zinc-400 leading-relaxed">
                        Intent-aware semantic caching and dynamic LLM routing. Ask a factual prompt or test semantic cache hits & safety guards.
                      </p>
                    </div>

                    {/* Suggestion Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full max-w-2xl pt-4">
                      {suggestions.map((s, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSendPrompt(s.prompt)}
                          className="p-3.5 rounded-xl bg-zinc-950/60 hover:bg-zinc-800/80 border border-zinc-800 hover:border-zinc-700 text-left transition-all group flex flex-col justify-between"
                        >
                          <div>
                            <span className="text-xs font-semibold text-emerald-400 block mb-1">{s.category}</span>
                            <p className="text-xs text-zinc-300 font-medium line-clamp-2">"{s.prompt}"</p>
                          </div>
                          <span className="text-[10px] text-zinc-500 block mt-2 group-hover:text-zinc-400 transition-colors">{s.subtitle}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Active Chat Threads */}
                {chatTurns.map((turn) => {
                  const payload = turn.responsePayload;
                  const source = payload?.source;
                  const tier = payload?.routing_decision?.tier;
                  const guardReason = payload?.guard_reason;

                  return (
                    <div key={turn.id} className="space-y-4">
                      {/* User Prompt Bubble */}
                      <div className="flex justify-end">
                        <div className="bg-zinc-800 text-zinc-100 rounded-2xl rounded-tr-sm px-4 py-3 max-w-[85%] text-sm shadow-sm border border-zinc-700/50">
                          {turn.prompt}
                        </div>
                      </div>

                      {/* Assistant Response Container */}
                      <div className="flex flex-col items-start max-w-[90%] space-y-2">
                        {/* Status Line */}
                        <div className="flex items-center gap-2 text-xs font-mono">
                          {source === 'cache' && (
                            <span className="inline-flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-md border border-emerald-500/20 font-medium">
                              <Zap className="w-3.5 h-3.5" />
                              Instant response from cache — {Math.round((payload.latency || 0) * 1000)}ms
                            </span>
                          )}

                          {source === 'llm' && guardReason && (
                            <span className="inline-flex items-center gap-1.5 text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20 font-medium">
                              <ShieldAlert className="w-3.5 h-3.5" />
                              Cache skipped for safety ({guardReason}) — {Math.round((payload.latency || 0) * 1000)}ms
                            </span>
                          )}

                          {source === 'llm' && !guardReason && tier === 'fast_cheap' && (
                            <span className="inline-flex items-center gap-1.5 text-sky-400 bg-sky-500/10 px-2.5 py-1 rounded-md border border-sky-500/20 font-medium">
                              <Sparkles className="w-3.5 h-3.5" />
                              Fresh response — routed to fast model — {Math.round((payload.latency || 0) * 1000)}ms
                            </span>
                          )}

                          {source === 'llm' && !guardReason && tier === 'capable_expensive' && (
                            <span className="inline-flex items-center gap-1.5 text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded-md border border-purple-500/20 font-medium">
                              <Sparkles className="w-3.5 h-3.5" />
                              Fresh response — routed to advanced model — {Math.round((payload.latency || 0) * 1000)}ms
                            </span>
                          )}

                          {source === 'error' && (
                            <span className="inline-flex items-center gap-1.5 text-rose-400 bg-rose-500/10 px-2.5 py-1 rounded-md border border-rose-500/20 font-medium">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              Gateway Error
                            </span>
                          )}
                        </div>

                        {/* Text Response Body */}
                        <div className="bg-zinc-950/70 border border-zinc-800 rounded-2xl rounded-tl-sm p-4 text-sm text-zinc-200 leading-relaxed w-full shadow-sm">
                          {payload.response}
                        </div>

                        {/* Collapsible Telemetry Details Drawer */}
                        <div className="w-full pt-1">
                          <button
                            onClick={() => toggleTurnDetails(turn.id)}
                            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors py-1"
                          >
                            <span>Telemetry Details</span>
                            {turn.showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          </button>

                          {turn.showDetails && (
                            <div className="mt-2 bg-zinc-950/90 border border-zinc-800/80 rounded-xl p-3.5 text-xs font-mono space-y-2 text-zinc-300">
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                <div>
                                  <span className="text-zinc-500 block">Similarity Score</span>
                                  <span className="font-semibold text-emerald-400">
                                    {payload.similarity_score !== null && payload.similarity_score !== undefined
                                      ? payload.similarity_score.toFixed(4)
                                      : 'N/A'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-zinc-500 block">Risk Score</span>
                                  <span className="font-semibold text-zinc-200">
                                    {payload.risk_assessment?.risk_score?.toFixed(2) ?? '0.00'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-zinc-500 block">Effective Threshold</span>
                                  <span className="font-semibold text-zinc-200">
                                    {payload.risk_assessment?.effective_threshold?.toFixed(4) ?? '0.0000'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-zinc-500 block">Provider / Model</span>
                                  <span className="font-semibold text-zinc-200">
                                    {payload.routing_decision?.provider} ({payload.routing_decision?.model})
                                  </span>
                                </div>
                                <div>
                                  <span className="text-zinc-500 block">Routing Tier</span>
                                  <span className="font-semibold text-zinc-200">
                                    {payload.routing_decision?.tier}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-zinc-500 block">Estimated Cost</span>
                                  <span className="font-semibold text-zinc-200">
                                    ${(payload.estimated_cost_usd || 0).toFixed(6)}
                                  </span>
                                </div>
                              </div>

                              {payload.routing_decision?.reasoning && (
                                <div className="pt-2 border-t border-zinc-800/80 text-[11px] text-zinc-400">
                                  <span className="text-zinc-500 font-semibold block">Routing Reasoning:</span>
                                  {payload.routing_decision.reasoning}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Submitting Spinner */}
                {submitting && (
                  <div className="flex items-center gap-3 text-xs text-zinc-400 font-mono py-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Evaluating risk & vector similarity...</span>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>
            </div>

            {/* Docked Single-Box Input Bar */}
            <div className="p-4 border-t border-zinc-800/60 bg-zinc-900/95 backdrop-blur-md">
              <div className="max-w-3xl mx-auto space-y-2">
                <div className="bg-zinc-950/80 border border-zinc-800 focus-within:border-emerald-500/60 rounded-2xl p-2 transition-all shadow-lg shadow-black/20">
                  <textarea
                    value={consoleInput}
                    onChange={(e) => setConsoleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendPrompt();
                      }
                    }}
                    placeholder="Send a prompt to SentinelCache..."
                    rows={2}
                    className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none px-3 py-1.5"
                  />

                  {/* Inline Controls & Mode Selection Pills */}
                  <div className="flex items-center justify-between pt-2 px-2 border-t border-zinc-800/50">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-zinc-500 font-mono mr-1">Mode:</span>
                      {(['hybrid', 'adaptive', 'fixed', 'disabled'] as const).map((m) => (
                        <button
                          key={m}
                          onClick={() => setConsoleMode(m)}
                          className={`px-2.5 py-1 rounded-md text-xs font-mono transition-all capitalize ${
                            consoleMode === m
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-semibold'
                              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => handleSendPrompt()}
                      disabled={!consoleInput.trim() || submitting}
                      className="p-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white transition-all shadow-md shadow-emerald-950/40"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <p className="text-[10px] text-center text-zinc-500 font-mono">
                  SentinelCache inspects query risk & vector distance before serving from Qdrant or routing to LLM providers.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ---------------------------------------------------------------- ---------------- */}
        {/* TAB 2: OBSERVABILITY DASHBOARD */}
        {/* ---------------------------------------------------------------- ---------------- */}
        {activeTab === 'dashboard' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="max-w-6xl mx-auto space-y-6">
              
              {/* Metric Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Total Requests</span>
                  <div className="text-2xl font-bold text-zinc-100 font-mono">{summary?.total_requests || 0}</div>
                  <div className="text-[11px] text-zinc-500 flex gap-2">
                    <span className="text-emerald-400">{summary?.hits || 0} hits</span>
                    <span>•</span>
                    <span>{summary?.misses || 0} misses</span>
                  </div>
                </div>

                <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Overall Hit Rate</span>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    {((summary?.overall_hit_rate || 0) * 100).toFixed(1)}%
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    {summary?.blocked_by_guard || 0} cache hits safety-blocked
                  </div>
                </div>

                <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Avg / Median Latency</span>
                  <div className="text-2xl font-bold text-zinc-100 font-mono">
                    {Math.round(summary?.avg_latency_ms || 0)}ms
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Median: {Math.round(summary?.median_latency_ms || 0)}ms | P95: {Math.round(summary?.p95_latency_ms || 0)}ms
                  </div>
                </div>

                <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Cost & Savings</span>
                  <div className="text-2xl font-bold text-emerald-400 font-mono">
                    +${(summary?.estimated_cost_saved_usd || 0).toFixed(4)}
                  </div>
                  <div className="text-[11px] text-zinc-500">
                    Spent: ${(summary?.total_cost_usd || 0).toFixed(4)}
                  </div>
                </div>
              </div>

              {/* System Performance Over Time (Linear Scatter-Dot Plot) */}
              <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-100">System Performance Over Time</h3>
                    <p className="text-xs text-zinc-400">Request volume, hit rate, and latency metrics</p>
                  </div>
                  <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800">
                    {(['1h', '24h', '7d'] as const).map(w => (
                      <button
                        key={w}
                        onClick={() => setWindow(w)}
                        className={`px-2.5 py-1 text-xs font-mono rounded-md transition-colors ${
                          window === w ? 'bg-zinc-800 text-zinc-100 font-semibold' : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                      >
                        {w}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="h-64 w-full pt-4">
                  {timeseries.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-xs text-zinc-500 font-mono">
                      Collecting telemetry data...
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={timeseries}>
                        <XAxis dataKey="timestamp" stroke="#52525b" fontSize={11} />
                        <YAxis yAxisId="left" stroke="#52525b" fontSize={11} />
                        <YAxis yAxisId="right" orientation="right" stroke="#52525b" fontSize={11} unit="ms" />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '0.5rem', fontSize: '12px' }}
                        />
                        <Line yAxisId="left" type="linear" dataKey="requests" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} name="Requests" />
                        <Line yAxisId="right" type="linear" dataKey="avg_latency_ms" stroke="#38bdf8" strokeWidth={2} dot={{ r: 4 }} name="Avg Latency (ms)" />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Recent Requests Table */}
              <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-5 space-y-4">
                <h3 className="text-sm font-semibold text-zinc-100">Live System Telemetry</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-400">
                        <th className="py-2.5 px-3">Time</th>
                        <th className="py-2.5 px-3">Prompt</th>
                        <th className="py-2.5 px-3">Outcome</th>
                        <th className="py-2.5 px-3">Sim. Score</th>
                        <th className="py-2.5 px-3">Risk</th>
                        <th className="py-2.5 px-3">Provider</th>
                        <th className="py-2.5 px-3">Latency</th>
                        <th className="py-2.5 px-3">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {recent.map((r) => (
                        <tr key={r.id} className="hover:bg-zinc-900/50 transition-colors">
                          <td className="py-2.5 px-3 text-zinc-500 whitespace-nowrap">
                            {new Date(r.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="py-2.5 px-3 text-zinc-200 max-w-xs truncate">
                            {r.prompt}
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            {r.cache_outcome === 'hit' && (
                              <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-semibold">HIT</span>
                            )}
                            {r.cache_outcome === 'miss' && (
                              <span className="text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded font-medium">MISS</span>
                            )}
                            {r.cache_outcome === 'blocked_by_guard' && (
                              <span className="text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 font-semibold">BLOCKED</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-emerald-400">
                            {r.similarity_score !== null && r.similarity_score !== undefined
                              ? r.similarity_score.toFixed(4)
                              : 'N/A'}
                          </td>
                          <td className="py-2.5 px-3 text-zinc-300">{r.risk_score.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-zinc-400 whitespace-nowrap">{r.provider}</td>
                          <td className="py-2.5 px-3 text-zinc-300 whitespace-nowrap">{Math.round(r.latency_ms)}ms</td>
                          <td className="py-2.5 px-3 text-zinc-400 whitespace-nowrap">${r.estimated_cost_usd.toFixed(6)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* ---------------------------------------------------------------- ---------------- */}
        {/* TAB 3: EVALUATION BENCHMARK MATRIX */}
        {/* ---------------------------------------------------------------- ---------------- */}
        {activeTab === 'evaluation' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="max-w-6xl mx-auto space-y-6">
              
              <div className="bg-zinc-950/80 border border-zinc-800 rounded-xl p-5 space-y-3">
                <h2 className="text-base font-bold text-zinc-100">Benchmark Evaluation Matrix (45 Test Pairs)</h2>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Comparative performance across cache evaluation modes: Disabled (Baseline), Fixed Threshold (0.92), Adaptive Risk Thresholding, and Hybrid (Adaptive + Negation/Entity Guards).
                </p>
              </div>

              {evalResults && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {Object.entries(evalResults).map(([m, r]) => (
                    <div key={m} className={`bg-zinc-950/90 border rounded-xl p-4 space-y-3 ${
                      m === 'hybrid' ? 'border-emerald-500/50 shadow-lg shadow-emerald-950/20' : 'border-zinc-800'
                    }`}>
                      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2">
                        <span className="font-semibold text-sm capitalize text-zinc-100">{r.mode} Mode</span>
                        {m === 'hybrid' && (
                          <span className="text-[10px] bg-emerald-500/20 text-emerald-300 font-mono px-2 py-0.5 rounded border border-emerald-500/30">
                            Production Default
                          </span>
                        )}
                      </div>

                      <div className="space-y-2 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Precision</span>
                          <span className="text-emerald-400 font-bold">{(r.precision * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Recall</span>
                          <span className="text-zinc-200">{(r.recall * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">False Positives (FP)</span>
                          <span className={`font-bold ${r.FP === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{r.FP}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">True Positives (TP)</span>
                          <span className="text-zinc-200">{r.TP}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Overall Hit Rate</span>
                          <span className="text-zinc-300">{(r.overall_hit_rate * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-zinc-500">Avg Latency</span>
                          <span className="text-zinc-300">{Math.round(r.avg_latency_ms)}ms</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </div>
          </div>
        )}

      </main>
    </div>
  );
}
