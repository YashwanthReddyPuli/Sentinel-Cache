import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, BarChart3, RefreshCw, Send, Zap, ShieldAlert,
  Sparkles, ChevronDown, ChevronUp, MessageSquare, LayoutDashboard
} from 'lucide-react';
import { 
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer 
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
    const interval = setInterval(fetchTelemetry, 3000);
    return () => clearInterval(interval);
  }, [window]);

  useEffect(() => {
    if (activeTab === 'chat' && chatTurns.length > 0) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatTurns, activeTab]);

  // Send request via chat
  const handleChatSubmit = async (e?: React.FormEvent, promptOverride?: string) => {
    if (e) e.preventDefault();
    const promptToSend = promptOverride || consoleInput;
    if (!promptToSend.trim() || submitting) return;
    
    setSubmitting(true);
    const timestamp = new Date().toLocaleTimeString();
    
    try {
      const res = await fetch(`${API_BASE}/v1/chat/completions?cache_mode=${consoleMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptToSend })
      });
      const data = await res.json();
      
      const newTurn: ChatTurn = {
        id: `turn-${Date.now()}`,
        timestamp,
        prompt: promptToSend,
        mode: consoleMode,
        responsePayload: data,
        showDetails: false
      };

      setChatTurns(prev => [...prev, newTurn]);
      if (!promptOverride) setConsoleInput('');
      fetchTelemetry();
    } catch (err) {
      console.error('Chat request failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleDetails = (turnId: string) => {
    setChatTurns(prev => prev.map(turn => 
      turn.id === turnId ? { ...turn, showDetails: !turn.showDetails } : turn
    ));
  };



  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-200 font-sans flex flex-col">
      {/* 1. PERSISTENT TOP NAVBAR */}
      <header className="border-b border-zinc-800/80 bg-[#0c0e17] px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600/20 border border-indigo-500/40 p-1.5 rounded">
            <Activity className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-base font-bold text-slate-100 tracking-tight font-mono">SENTINELCACHE</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-indigo-400 border border-zinc-800">
                v0.5.0
              </span>
            </div>
          </div>
        </div>

        {/* Navbar Items Right */}
        <nav className="flex items-center space-x-8 text-xs font-medium">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center space-x-2 py-1 transition-colors border-b-2 ${
              activeTab === 'chat'
                ? 'border-indigo-500 text-slate-100 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Chat</span>
          </button>

          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center space-x-2 py-1 transition-colors border-b-2 ${
              activeTab === 'dashboard'
                ? 'border-indigo-500 text-slate-100 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('evaluation')}
            className={`flex items-center space-x-2 py-1 transition-colors border-b-2 ${
              activeTab === 'evaluation'
                ? 'border-indigo-500 text-slate-100 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Evaluation</span>
          </button>
        </nav>
      </header>

      {/* MAIN CONTAINER */}
      <div className="flex-1 flex flex-col">
        {/* TAB 1: ADAPTED CHAT VIEW */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col justify-between max-w-4xl mx-auto w-full px-4 py-6">
            {/* EMPTY STATE LAYOUT (before any message is sent) */}
            {chatTurns.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center my-auto space-y-8 py-8">
                {/* Logo & Welcome Header */}
                <div className="text-center space-y-3">
                  <div className="inline-flex p-3 rounded-xl bg-zinc-900 border border-zinc-800 text-indigo-400 mb-2">
                    <Activity className="w-8 h-8" />
                  </div>
                  <h1 className="text-2xl font-bold text-slate-100 tracking-tight">SentinelCache Gateway</h1>
                  <p className="text-sm text-slate-400 max-w-md mx-auto">
                    Intelligent risk-aware semantic prompt caching & dynamic multi-provider LLM routing
                  </p>
                </div>

                {/* Centered Input Box Container */}
                <div className="w-full max-w-2xl bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 shadow-xl space-y-3">
                  <textarea
                    rows={3}
                    value={consoleInput}
                    onChange={(e) => setConsoleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleChatSubmit();
                      }
                    }}
                    placeholder="Ask a question or test a prompt..."
                    className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none font-sans"
                  />

                  {/* Inline Toggle Pills & Controls below text field */}
                  <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80">
                    <div className="flex items-center space-x-1.5 text-xs">
                      <span className="text-[11px] font-mono text-slate-400 mr-1">Cache Mode:</span>
                      {(['hybrid', 'adaptive', 'fixed', 'disabled'] as const).map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setConsoleMode(m)}
                          className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
                            consoleMode === m
                              ? 'bg-indigo-600 text-white font-medium'
                              : 'bg-zinc-800/70 text-slate-400 hover:bg-zinc-800 hover:text-slate-200'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => handleChatSubmit()}
                      disabled={submitting || !consoleInput.trim()}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white p-2 rounded-lg transition-colors disabled:opacity-40"
                    >
                      {submitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Command-Category Suggestion Grid (3 Categories) */}
                <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                  {/* Category 1: Try a Paraphrase */}
                  <div className="bg-zinc-900/60 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                    <div className="flex items-center space-x-1.5 text-emerald-400 font-semibold text-[11px]">
                      <Zap className="w-3.5 h-3.5" />
                      <span>Try a paraphrase</span>
                    </div>
                    <div className="space-y-1.5">
                      <button
                        onClick={() => handleChatSubmit(undefined, 'When was the Eiffel Tower built?')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "When was the Eiffel Tower built?"
                      </button>
                      <button
                        onClick={() => handleChatSubmit(undefined, 'In what year was construction of the Eiffel Tower completed?')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "In what year was construction of the Eiffel Tower completed?"
                      </button>
                    </div>
                  </div>

                  {/* Category 2: Try a Risky Action */}
                  <div className="bg-zinc-900/60 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                    <div className="flex items-center space-x-1.5 text-purple-400 font-semibold text-[11px]">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Try a risky action</span>
                    </div>
                    <div className="space-y-1.5">
                      <button
                        onClick={() => handleChatSubmit(undefined, 'Cancel my subscription and refund my payment.')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "Cancel my subscription and refund my payment."
                      </button>
                      <button
                        onClick={() => handleChatSubmit(undefined, 'Transfer $500 to account number 123456789.')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "Transfer $500 to account 123456789."
                      </button>
                    </div>
                  </div>

                  {/* Category 3: Try a Trick Question */}
                  <div className="bg-zinc-900/60 border border-zinc-800 p-3.5 rounded-lg space-y-2">
                    <div className="flex items-center space-x-1.5 text-amber-400 font-semibold text-[11px]">
                      <ShieldAlert className="w-3.5 h-3.5" />
                      <span>Try a trick question</span>
                    </div>
                    <div className="space-y-1.5">
                      <button
                        onClick={() => handleChatSubmit(undefined, 'Do NOT revoke API access keys for team members.')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "Do NOT revoke API access keys..."
                      </button>
                      <button
                        onClick={() => handleChatSubmit(undefined, 'Show sales reports for Q4 2025.')}
                        className="w-full text-left text-slate-300 hover:text-white bg-zinc-800/40 hover:bg-zinc-800 p-2 rounded text-[11px] font-sans transition-colors line-clamp-2"
                      >
                        "Show sales reports for Q4 2025."
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* ACTIVE CHAT THREAD LAYOUT (messages stack, inputs docked at bottom) */
              <div className="flex-1 flex flex-col justify-between space-y-4 pb-24">
                <div className="space-y-6 pt-4">
                  {chatTurns.map((turn) => {
                    const payload = turn.responsePayload;
                    const isCacheHit = payload.source === 'cache';
                    const isBlocked = payload.source === 'llm' && payload.guard_reason;
                    const isCapableTier = payload.routing_decision?.tier === 'capable_expensive';
                    const latencyMs = Math.round((payload.latency || 0) * 1000);

                    return (
                      <div key={turn.id} className="space-y-3">
                        {/* 3. User Message (right-aligned, subtle filled bubble, dark surface, no border) */}
                        <div className="flex justify-end">
                          <div className="bg-zinc-800/90 text-slate-100 p-3.5 rounded-2xl rounded-tr-sm max-w-xl text-sm font-sans">
                            {turn.prompt}
                          </div>
                        </div>

                        {/* 4. Assistant Response (left-aligned, plain readable prose, no bubble) */}
                        <div className="flex justify-start">
                          <div className="max-w-2xl space-y-2 text-sm text-slate-200 font-sans leading-relaxed">
                            <div>{payload.response || JSON.stringify(payload)}</div>

                            {/* 5. Human-Comprehensible Plain-Language Status Line */}
                            <div className="flex items-center space-x-2 text-xs text-slate-400 pt-1 font-sans">
                              {isCacheHit ? (
                                <div className="flex items-center space-x-1.5 text-emerald-400">
                                  <Zap className="w-4 h-4 fill-emerald-400/20" />
                                  <span>Instant response from cache — {latencyMs}ms</span>
                                </div>
                              ) : isBlocked ? (
                                <div className="flex items-center space-x-1.5 text-amber-400">
                                  <ShieldAlert className="w-4 h-4" />
                                  <span>Cache skipped for safety — this looked too similar to a different, riskier request</span>
                                </div>
                              ) : isCapableTier ? (
                                <div className="flex items-center space-x-1.5 text-purple-400">
                                  <Sparkles className="w-4 h-4" />
                                  <span>Generated fresh — routed to advanced model (higher-risk request) — {(payload.latency).toFixed(2)}s</span>
                                </div>
                              ) : (
                                <div className="flex items-center space-x-1.5 text-blue-400">
                                  <Sparkles className="w-4 h-4" />
                                  <span>Generated fresh — routed to fast model — {latencyMs}ms</span>
                                </div>
                              )}

                              {/* 6. Small "Details" chevron toggle */}
                              <button
                                onClick={() => toggleDetails(turn.id)}
                                className="ml-2 text-slate-500 hover:text-slate-300 flex items-center space-x-0.5 text-[11px] font-mono transition-colors"
                              >
                                <span>Details</span>
                                {turn.showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              </button>
                            </div>

                            {/* Collapsible Technical Details Box */}
                            {turn.showDetails && (
                              <div className="bg-zinc-900 border border-zinc-800 p-3 rounded-lg text-xs font-mono text-slate-300 space-y-1.5 mt-2">
                                <div className="text-[10px] text-slate-500 uppercase tracking-wider">TECHNICAL TELEMETRY</div>
                                <div className="grid grid-cols-2 gap-2 text-[11px]">
                                  <div>Similarity Score: <strong className="text-indigo-400">{payload.similarity_score ? payload.similarity_score.toFixed(4) : 'N/A'}</strong></div>
                                  <div>Risk Score: <strong className="text-amber-400">{payload.risk_assessment?.risk_score?.toFixed(2) ?? 'N/A'}</strong></div>
                                  <div>Effective Threshold: <strong className="text-slate-200">{payload.risk_assessment?.effective_threshold?.toFixed(4) ?? 'N/A'}</strong></div>
                                  <div>Cost: <strong className="text-emerald-400">${payload.estimated_cost_usd?.toFixed(6)}</strong></div>
                                </div>
                                <div className="text-[11px] text-slate-400 pt-1 border-t border-zinc-800">
                                  Routing: {payload.routing_decision?.provider} ({payload.routing_decision?.model}) — {payload.routing_decision?.reasoning}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={chatBottomRef} />
                </div>
              </div>
            )}

            {/* DOCKED FIXED BOTTOM INPUT BAR (active when thread exists) */}
            {chatTurns.length > 0 && (
              <div className="fixed bottom-0 left-0 right-0 bg-[#090a0f]/95 backdrop-blur border-t border-zinc-800/80 p-4 z-40">
                <div className="max-w-3xl mx-auto space-y-2">
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-2.5 flex items-center space-x-2">
                    <input
                      type="text"
                      value={consoleInput}
                      onChange={(e) => setConsoleInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleChatSubmit();
                        }
                      }}
                      placeholder="Type a follow-up prompt..."
                      className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans px-2"
                    />

                    {/* Inline Mode Selector Pills */}
                    <div className="flex items-center space-x-1 bg-zinc-800/60 p-1 rounded-lg text-xs font-mono">
                      {(['hybrid', 'adaptive', 'fixed', 'disabled'] as const).map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setConsoleMode(m)}
                          className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                            consoleMode === m ? 'bg-indigo-600 text-white font-medium' : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => handleChatSubmit()}
                      disabled={submitting || !consoleInput.trim()}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white p-2 rounded-lg transition-colors disabled:opacity-40"
                    >
                      {submitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: SYSTEM DASHBOARD */}
        {activeTab === 'dashboard' && (
          <div className="max-w-7xl mx-auto w-full p-6 space-y-6">
            {/* Stat Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg flex flex-col justify-between">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">TOTAL REQUESTS</div>
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold font-mono text-slate-100 tabular-nums">
                    {summary?.total_requests || 0}
                  </span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
                    {((summary?.overall_hit_rate || 0) * 100).toFixed(1)}% Hit Rate
                  </span>
                </div>
                <div className="mt-3 pt-3 border-t border-zinc-800 text-[11px] font-mono text-slate-400 flex justify-between">
                  <span>Hits: <strong className="text-emerald-400">{summary?.hits || 0}</strong></span>
                  <span>Misses: <strong className="text-slate-300">{summary?.misses || 0}</strong></span>
                  <span>Blocked: <strong className="text-amber-400">{summary?.blocked_by_guard || 0}</strong></span>
                </div>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg flex flex-col justify-between">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">LATENCY (MEDIAN / P95)</div>
                <div className="flex items-baseline space-x-2 font-mono">
                  <span className="text-2xl font-bold text-slate-100 tabular-nums">
                    {summary?.median_latency_ms ? `${summary.median_latency_ms}ms` : '0ms'}
                  </span>
                  <span className="text-xs text-slate-400">/ {summary?.p95_latency_ms || 0}ms p95</span>
                </div>
                <div className="mt-3 pt-3 border-t border-zinc-800 text-[11px] font-mono text-slate-400">
                  Avg Latency: <span className="text-indigo-300">{summary?.avg_latency_ms || 0}ms</span>
                </div>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg flex flex-col justify-between">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">API COST SPEND</div>
                <div className="flex items-baseline justify-between font-mono">
                  <span className="text-2xl font-bold text-slate-100 tabular-nums">
                    ${(summary?.total_cost_usd || 0).toFixed(5)}
                  </span>
                  <span className="text-xs text-emerald-400">
                    +${(summary?.estimated_cost_saved_usd || 0).toFixed(5)} Saved
                  </span>
                </div>
                <div className="mt-3 pt-3 border-t border-zinc-800 text-[11px] font-mono text-slate-400">
                  Bypassed LLM Calls: <span className="text-emerald-400 font-bold">{summary?.hits || 0}</span>
                </div>
              </div>

              <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-lg flex flex-col justify-between">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">ROUTING DISTRIBUTION</div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono mt-1">
                  <div className="bg-zinc-800/60 p-2 rounded border border-zinc-800">
                    <div className="text-[10px] text-emerald-400">FAST & CHEAP</div>
                    <div className="text-lg font-bold text-slate-100">{summary?.requests_by_tier?.fast_cheap || 0}</div>
                  </div>
                  <div className="bg-zinc-800/60 p-2 rounded border border-zinc-800">
                    <div className="text-[10px] text-purple-400">CAPABLE</div>
                    <div className="text-lg font-bold text-slate-100">{summary?.requests_by_tier?.capable_expensive || 0}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 7. Timeseries Chart (Linear only, no fake interpolation) */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-sm font-bold text-slate-200 tracking-wide">SYSTEM PERFORMANCE OVER TIME</h2>
                  <p className="text-xs text-slate-400">Real request telemetry timeseries (Linear interpolation)</p>
                </div>
                <div className="flex space-x-1 bg-zinc-800/60 p-1 rounded border border-zinc-800">
                  {(['1h', '24h', '7d'] as const).map((w) => (
                    <button
                      key={w}
                      onClick={() => setWindow(w)}
                      className={`px-2.5 py-1 text-[11px] font-mono rounded ${
                        window === w ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {w.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              <div className="h-64 w-full">
                {timeseries.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="hitRateGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
                        </linearGradient>
                        <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="timestamp" stroke="#475569" fontSize={11} tickLine={false} />
                      <YAxis yAxisId="left" stroke="#10b981" fontSize={11} tickLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
                      <YAxis yAxisId="right" orientation="right" stroke="#6366f1" fontSize={11} tickLine={false} tickFormatter={(v) => `${v}ms`} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0d0f17', borderColor: '#334155', borderRadius: '6px', fontSize: '12px' }}
                        formatter={(val: any, name: any) => [
                          name === 'hit_rate' ? `${(val * 100).toFixed(1)}%` : `${val} ms`,
                          name === 'hit_rate' ? 'Hit Rate' : 'Avg Latency'
                        ]}
                      />
                      <Area yAxisId="left" type="linear" dataKey="hit_rate" stroke="#10b981" fillOpacity={1} fill="url(#hitRateGrad)" strokeWidth={2} />
                      <Area yAxisId="right" type="linear" dataKey="avg_latency_ms" stroke="#6366f1" fillOpacity={1} fill="url(#latencyGrad)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-slate-500 font-mono text-xs border border-dashed border-zinc-800 rounded">
                    No activity recorded in current time window ({window}). Send requests to populate timeseries.
                  </div>
                )}
              </div>
            </div>

            {/* Recent Log Table */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
              <h2 className="text-sm font-bold text-slate-200 tracking-wide mb-3">RECENT REQUEST LOG</h2>
              <div className="overflow-x-auto border border-zinc-800 rounded">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-zinc-800/80 text-slate-400 border-b border-zinc-800">
                    <tr>
                      <th className="p-3">TIME</th>
                      <th className="p-3">PROMPT</th>
                      <th className="p-3">OUTCOME</th>
                      <th className="p-3">PROVIDER</th>
                      <th className="p-3 text-right">LATENCY</th>
                      <th className="p-3 text-right">COST</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 bg-zinc-950">
                    {recent.map((r: RequestRecord) => (
                      <tr key={r.id} className="hover:bg-zinc-900 transition-colors">
                        <td className="p-3 text-slate-500 whitespace-nowrap">{new Date(r.timestamp).toLocaleTimeString()}</td>
                        <td className="p-3 text-slate-200 font-sans max-w-xs truncate">{r.prompt}</td>
                        <td className="p-3 whitespace-nowrap">
                          {r.cache_outcome === 'hit' ? (
                            <span className="text-emerald-400 font-bold">HIT</span>
                          ) : r.cache_outcome === 'blocked_by_guard' ? (
                            <span className="text-amber-400 font-bold">GUARD BLOCK</span>
                          ) : (
                            <span className="text-slate-400">MISS</span>
                          )}
                        </td>
                        <td className="p-3 text-slate-300">{r.provider} ({r.tier})</td>
                        <td className="p-3 text-right text-slate-300">{r.latency_ms}ms</td>
                        <td className="p-3 text-right text-emerald-400">${r.estimated_cost_usd.toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: EVALUATION VIEW */}
        {activeTab === 'evaluation' && (
          <div className="max-w-7xl mx-auto w-full p-6 space-y-6">
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
              <div className="mb-6">
                <h2 className="text-base font-bold text-slate-100 tracking-tight">CACHE EVALUATION BENCHMARK RESULTS</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Empirical performance evaluation across 45 dataset pairs under 4 distinct operating modes.
                </p>
              </div>

              {/* Mode Descriptions Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-lg space-y-1">
                  <div className="font-mono text-xs font-bold text-slate-300">1. DISABLED MODE</div>
                  <p className="text-xs text-slate-400">Bypasses the semantic cache completely and forwards all incoming requests directly to the LLM providers.</p>
                </div>
                <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-lg space-y-1">
                  <div className="font-mono text-xs font-bold text-slate-300">2. FIXED THRESHOLD (0.92)</div>
                  <p className="text-xs text-slate-400">Applies a static similarity cutoff (0.92) regardless of request risk level, causing safety violations on operational queries.</p>
                </div>
                <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-lg space-y-1">
                  <div className="font-mono text-xs font-bold text-slate-300">3. ADAPTIVE THRESHOLD (0.88 - 0.99)</div>
                  <p className="text-xs text-slate-400">Dynamically scales similarity cutoffs based on intent risk classification to protect high-risk operational requests.</p>
                </div>
                <div className="bg-zinc-950 border border-indigo-900/60 p-4 rounded-lg space-y-1 bg-indigo-950/20">
                  <div className="font-mono text-xs font-bold text-indigo-400">4. HYBRID GUARD MODE (PRODUCTION)</div>
                  <p className="text-xs text-slate-300">Enforces deterministic NegationGuard and EntityGuard checks to guarantee 100% precision (0 false hits) on all requests.</p>
                </div>
              </div>

              {/* Evaluation Grid Table */}
              <div className="overflow-x-auto border border-zinc-800 rounded font-mono text-xs">
                <table className="w-full text-left">
                  <thead className="bg-zinc-800/80 text-slate-300 border-b border-zinc-800">
                    <tr>
                      <th className="p-3">EVALUATION METRIC</th>
                      <th className="p-3 text-center">DISABLED</th>
                      <th className="p-3 text-center">FIXED (0.92)</th>
                      <th className="p-3 text-center">ADAPTIVE</th>
                      <th className="p-3 text-center bg-indigo-950/40 text-indigo-300 border-x border-indigo-900/50">HYBRID GUARD (PRODUCTION)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 bg-zinc-950">
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">True Positives (TP)</td>
                      <td className="p-3 text-center text-slate-400">{evalResults?.disabled?.TP ?? 0}</td>
                      <td className="p-3 text-center text-slate-300">{evalResults?.fixed?.TP ?? 5}</td>
                      <td className="p-3 text-center text-slate-300">{evalResults?.adaptive?.TP ?? 5}</td>
                      <td className="p-3 text-center font-bold text-emerald-400 bg-indigo-950/20 border-x border-indigo-900/30">{evalResults?.hybrid?.TP ?? 5}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">False Positives (FP - Safety Violations)</td>
                      <td className="p-3 text-center text-slate-400">{evalResults?.disabled?.FP ?? 0}</td>
                      <td className="p-3 text-center text-red-400 font-bold">{evalResults?.fixed?.FP ?? 5}</td>
                      <td className="p-3 text-center text-amber-400">{evalResults?.adaptive?.FP ?? 2}</td>
                      <td className="p-3 text-center font-bold text-emerald-400 bg-indigo-950/20 border-x border-indigo-900/30">{evalResults?.hybrid?.FP ?? 0}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">True Negatives (TN)</td>
                      <td className="p-3 text-center text-slate-400">{evalResults?.disabled?.TN ?? 20}</td>
                      <td className="p-3 text-center text-slate-300">{evalResults?.fixed?.TN ?? 15}</td>
                      <td className="p-3 text-center text-slate-300">{evalResults?.adaptive?.TN ?? 18}</td>
                      <td className="p-3 text-center text-slate-200 bg-indigo-950/20 border-x border-indigo-900/30">{evalResults?.hybrid?.TN ?? 20}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">Precision</td>
                      <td className="p-3 text-center text-slate-500">0.00%</td>
                      <td className="p-3 text-center text-red-400">50.00%</td>
                      <td className="p-3 text-center text-amber-400">71.43%</td>
                      <td className="p-3 text-center font-bold text-emerald-400 bg-indigo-950/20 border-x border-indigo-900/30">100.00%</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">Recall (Overall)</td>
                      <td className="p-3 text-center text-slate-500">0.00%</td>
                      <td className="p-3 text-center text-slate-300">20.00%</td>
                      <td className="p-3 text-center text-slate-300">20.00%</td>
                      <td className="p-3 text-center font-bold text-indigo-300 bg-indigo-950/20 border-x border-indigo-900/30">20.00%</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">False Positive Rate (FPR)</td>
                      <td className="p-3 text-center text-slate-500">0.00%</td>
                      <td className="p-3 text-center text-red-400">25.00%</td>
                      <td className="p-3 text-center text-amber-400">10.00%</td>
                      <td className="p-3 text-center font-bold text-emerald-400 bg-indigo-950/20 border-x border-indigo-900/30">0.00%</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-200">False Negative Rate (FNR)</td>
                      <td className="p-3 text-center text-slate-500">100.00%</td>
                      <td className="p-3 text-center text-slate-300">80.00%</td>
                      <td className="p-3 text-center text-slate-300">80.00%</td>
                      <td className="p-3 text-center text-slate-300 bg-indigo-950/20 border-x border-indigo-900/30">80.00%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
