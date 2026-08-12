'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, MessageSquare, RotateCcw, Globe, Search, ShieldAlert, ListChecks, Loader2, PanelLeft, ChevronDown, Clock } from 'lucide-react';
import { streamChat } from '@/lib/chat-api';
import { listThreads, getThreadHistory, deleteThread, type ThreadMeta } from '@/lib/threads-api';
import { getSession } from '@/lib/auth';
import { useOnlineStatus } from '@/lib/useOnlineStatus';
import { queueMessage, replayQueuedMessages, type QueuedMessage } from '@/lib/message-queue';
import ErrorBoundary from '@/components/ErrorBoundary';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import ItineraryCard from '@/components/ItineraryCard';
import OfflineBanner from '@/components/OfflineBanner';
import ComparisonView from './ComparisonView';
import ThreadSidebar from './ThreadSidebar';
import type { ChatMessage, ComparisonData, Itinerary } from '@/lib/types';

const THREAD_STORAGE_KEY = 'voyagerai_chat_thread_id';

const TOOL_LABELS: Record<string, string> = {
  researcher: 'Researching',
  risk_detector: 'Checking risks',
  constraint_analyzer: 'Checking constraints',
  validator: 'Validating',
  enricher: 'Adding local tips',
  cost_optimizer: 'Optimizing budget',
  multi_plan_generator: 'Generating plans',
  quality_scorer: 'Scoring quality',
};

const TOOL_ICONS: Record<string, React.ReactNode> = {
  researcher: <Search className="w-3 h-3" />,
  risk_detector: <ShieldAlert className="w-3 h-3" />,
  constraint_analyzer: <ListChecks className="w-3 h-3" />,
  multi_plan_generator: <Globe className="w-3 h-3" />,
  quality_scorer: <ListChecks className="w-3 h-3" />,
};

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'welcome',
    role: 'assistant',
    content: "Hi! I'm your AI travel planner. Tell me about the trip you're dreaming of — where would you like to go, for how long, and what's your budget?",
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState('');
  const [streamingItinerary, setStreamingItinerary] = useState<Itinerary | null>(null);
  const [streamingComparison, setStreamingComparison] = useState<ComparisonData | null>(null);
  const [activeWorkers, setActiveWorkers] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(THREAD_STORAGE_KEY);
    }
    return null;
  });
  const [showSidebar, setShowSidebar] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [hasMoreThreads, setHasMoreThreads] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const isOnline = useOnlineStatus();
  const [pendingMessages, setPendingMessages] = useState<QueuedMessage[]>([]);
  const [replaying, setReplaying] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const sendingRef = useRef(false);
  const sessionResetRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSession().then((user) => {
      if (!user) {
        window.location.href = '/login';
        return;
      }
      setAuthChecked(true);
      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    });
  }, []);

  // Auto-scroll only when user is at bottom
  useEffect(() => {
    if (isAtBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, streamingText, isAtBottom]);

  // Elapsed timer for typing indicator
  useEffect(() => {
    if (!loading) {
      return;
    }
    const interval = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [loading]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSidebarOpen(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setIsAtBottom(atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setIsAtBottom(true);
  }, []);

  const handleNewChat = () => {
    abortRef.current?.abort();
    sessionResetRef.current = true;
    setSidebarOpen(false);
    setMessages([{
      id: 'welcome',
      role: 'assistant',
      content: "Hi! I'm your AI travel planner. Tell me about the trip you're dreaming of — where would you like to go, for how long, and what's your budget?",
    }]);
    setThreadId(null);
    localStorage.removeItem(THREAD_STORAGE_KEY);
    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setActiveWorkers([]);
  };

  const handleSelectThread = async (selectedThreadId: string) => {
    if (selectedThreadId === threadId) return;

    abortRef.current?.abort();
    setLoadingHistory(true);
    setThreadId(selectedThreadId);
    setSidebarOpen(false);
    try {
      localStorage.setItem(THREAD_STORAGE_KEY, selectedThreadId);
    } catch {
      // storage unavailable
    }

    const history = await getThreadHistory(selectedThreadId);
    const historyMessages: ChatMessage[] = history.map((msg, i) => ({
      id: `history-${i}`,
      role: msg.role,
      content: msg.content,
      itinerary: msg.itinerary,
      comparison: msg.comparison,
    }));

    if (historyMessages.length === 0) {
      setMessages([{
        id: 'welcome',
        role: 'assistant',
        content: "Hi! I'm your AI travel planner. Tell me about the trip you're dreaming of — where would you like to go, for how long, and what's your budget?",
      }]);
    } else {
      setMessages(historyMessages);
    }

    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setActiveWorkers([]);
    setLoadingHistory(false);
  };

  const handleDeleteThread = async (threadIdToDelete: string) => {
    const ok = await deleteThread(threadIdToDelete);
    if (ok) {
      setThreads((prev) => prev.filter((t) => t.thread_id !== threadIdToDelete));
      if (threadIdToDelete === threadId) {
        handleNewChat();
      }
    }
  };

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading || sendingRef.current) return;

    // If offline, queue the message instead of sending
    if (!isOnline) {
      const queued = await queueMessage(threadId, text);
      setPendingMessages((prev) => [...prev, queued]);
      setInput('');
      return;
    }

    sendingRef.current = true;
    sessionResetRef.current = false;
    setInput('');
    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setActiveWorkers([]);

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMessage]);

    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }]);

    setLoading(true);
    setElapsed(0);

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedText = '';
    let accumulatedItinerary: Itinerary | null = null;
    let accumulatedComparison: ComparisonData | null = null;
    let streamFailed = false;
    let errorMessage = '';
    let aborted = false;

    try {
      const newThreadId = await streamChat(
        { message: text, thread_id: threadId ?? undefined },
        {
          signal: controller.signal,
          onToken: (token) => {
            accumulatedText += token;
            setStreamingText(accumulatedText);
          },
          onItinerary: (itinerary) => {
            accumulatedItinerary = itinerary;
            setStreamingItinerary(itinerary);
          },
          onComparison: (data) => {
            accumulatedComparison = data;
            setStreamingComparison(data);
          },
          onThreadId: (tid) => {
            if (sessionResetRef.current) return;
            setThreadId(tid);
            try {
              localStorage.setItem(THREAD_STORAGE_KEY, tid);
            } catch {
              // storage unavailable — thread id still works for this session
            }
          },
          onStatus: (status) => {
            const tool = status.tool;
            if (!TOOL_LABELS[tool]) return;
            setActiveWorkers((prev) =>
              status.status === 'running'
                ? prev.includes(tool) ? prev : [...prev, tool]
                : prev.filter((t) => t !== tool),
            );
          },
          onError: (msg) => {
            streamFailed = true;
            errorMessage = msg;
            setError(msg);
          },
          onAbort: () => {
            aborted = true;
          },
        },
      );

      if (sessionResetRef.current) return;

      setMessages((prev) => {
        const updated = [...prev];
        const idx = updated.findIndex((m) => m.id === assistantId);
        if (idx !== -1) {
          if (streamFailed && !accumulatedText) {
            updated[idx] = {
              ...updated[idx],
              content: `⚠ Generation failed: ${errorMessage || 'unknown error'}`,
            };
          } else if (aborted && !accumulatedText) {
            updated[idx] = { ...updated[idx], content: '⏹ Generation stopped.' };
          } else {
            updated[idx] = {
              ...updated[idx],
              content: accumulatedText,
              itinerary: accumulatedItinerary ?? undefined,
              comparison: accumulatedComparison ?? undefined,
            };
          }
        }
        return updated;
      });

      setStreamingText('');
      setStreamingItinerary(null);
      setStreamingComparison(null);

      if (newThreadId && !sessionResetRef.current) {
        setThreadId(newThreadId);
        try {
          localStorage.setItem(THREAD_STORAGE_KEY, newThreadId);
        } catch {
          // storage unavailable — thread id still works for this session
        }
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
      setActiveWorkers([]);
      sendingRef.current = false;
      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    }
  }, [input, loading, threadId, isOnline]);

  // Replay queued messages when back online
  useEffect(() => {
    if (!isOnline || replaying) return;
    let cancelled = false;

    (async () => {
      const { getQueuedMessages } = await import('@/lib/offline-db');
      const queued = await getQueuedMessages();
      if (queued.length === 0 || cancelled) return;

      setReplaying(true);
      const sentCount = await replayQueuedMessages(async (msg) => {
        // Remove from pending UI
        setPendingMessages((prev) => prev.filter((p) => p.id !== msg.id));

        // Add user message to UI
        const userMessage: ChatMessage = {
          id: `replay-${msg.id}`,
          role: 'user',
          content: msg.content,
        };
        setMessages((prev) => [...prev, userMessage]);

        const assistantId = `replay-assistant-${msg.id}`;
        setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '' }]);
        setLoading(true);

        try {
          let accumulatedText = '';
          let accumulatedItinerary: Itinerary | null = null;
          let accumulatedComparison: ComparisonData | null = null;
          let streamFailed = false;
          let errorMessage = '';

          await streamChat(
            { message: msg.content, thread_id: msg.thread_id ?? undefined },
            {
              onToken: (token) => {
                accumulatedText += token;
                setStreamingText(accumulatedText);
              },
              onItinerary: (itinerary) => {
                accumulatedItinerary = itinerary;
                setStreamingItinerary(itinerary);
              },
              onComparison: (data) => {
                accumulatedComparison = data;
                setStreamingComparison(data);
              },
              onThreadId: (tid) => {
                if (sessionResetRef.current) return;
                setThreadId(tid);
                try {
                  localStorage.setItem(THREAD_STORAGE_KEY, tid);
                } catch {
                  // storage unavailable
                }
              },
              onStatus: (status) => {
                const tool = status.tool;
                if (!TOOL_LABELS[tool]) return;
                setActiveWorkers((prev) =>
                  status.status === 'running'
                    ? prev.includes(tool) ? prev : [...prev, tool]
                    : prev.filter((t) => t !== tool),
                );
              },
              onError: (msg) => {
                streamFailed = true;
                errorMessage = msg;
                setError(msg);
              },
            },
          );

          setMessages((prev) => {
            const updated = [...prev];
            const idx = updated.findIndex((m) => m.id === assistantId);
            if (idx !== -1) {
              if (streamFailed && !accumulatedText) {
                updated[idx] = {
                  ...updated[idx],
                  content: `⚠ Generation failed: ${errorMessage || 'unknown error'}`,
                };
              } else {
                updated[idx] = {
                  ...updated[idx],
                  content: accumulatedText,
                  itinerary: accumulatedItinerary ?? undefined,
                  comparison: accumulatedComparison ?? undefined,
                };
              }
            }
            return updated;
          });

          setStreamingText('');
          setStreamingItinerary(null);
          setStreamingComparison(null);
          setLoading(false);
          setActiveWorkers([]);
          return true;
        } catch {
          setLoading(false);
          setActiveWorkers([]);
          return false;
        }
      });

      if (!cancelled) {
        setReplaying(false);
        if (sentCount > 0) {
          listThreads().then((res) => {
            setThreads(res.threads);
            setHasMoreThreads(res.has_more);
          });
        }
      }
    })();

    return () => { cancelled = true; };
  }, [isOnline, replaying]);

  const handleSelectPlan = useCallback((tier: string) => {
    setInput(`I'll go with the ${tier} plan`);
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!authChecked) {
    return (
      <main className="min-h-screen flex items-center justify-center pt-16">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </main>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden pt-16 flex flex-col">
      <OfflineBanner replaying={replaying} />
      {/* Background gradients */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-indigo-400/[0.06] rounded-full blur-[120px] animate-aurora" />
        <div className="absolute bottom-0 left-1/4 w-[500px] h-[500px] bg-violet-400/[0.04] rounded-full blur-[100px] animate-float-slow" />
      </div>

      {/* Grid overlay */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10 flex flex-1 overflow-hidden">
        {/* Desktop sidebar (inline) */}
        <AnimatePresence initial={false}>
          {showSidebar && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="hidden md:block overflow-hidden"
            >
              <ThreadSidebar
                threads={threads}
                activeThreadId={threadId}
                loadingHistory={loadingHistory}
                hasMore={hasMoreThreads}
                loadingMore={loadingMore}
                onSelect={handleSelectThread}
                onDelete={handleDeleteThread}
                onNewChat={handleNewChat}
                onLoadMore={async () => {
                  setLoadingMore(true);
                  const res = await listThreads(threads.length);
                  setThreads((prev) => [...prev, ...res.threads]);
                  setHasMoreThreads(res.has_more);
                  setLoadingMore(false);
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Mobile sidebar (overlay) */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-50 md:hidden"
              role="dialog"
              aria-modal="true"
              aria-label="Conversation history"
            >
              <div className="absolute inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
              <motion.div
                initial={{ x: -260 }}
                animate={{ x: 0 }}
                exit={{ x: -260 }}
                transition={{ duration: 0.2 }}
                className="absolute left-0 top-0 h-full w-[260px]"
              >
                <ThreadSidebar
                  threads={threads}
                  activeThreadId={threadId}
                  loadingHistory={loadingHistory}
                  hasMore={hasMoreThreads}
                  loadingMore={loadingMore}
                  onSelect={handleSelectThread}
                  onDelete={handleDeleteThread}
                  onNewChat={handleNewChat}
                  onLoadMore={async () => {
                    setLoadingMore(true);
                    const res = await listThreads(threads.length);
                    setThreads((prev) => [...prev, ...res.threads]);
                    setHasMoreThreads(res.has_more);
                    setLoadingMore(false);
                  }}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex flex-col flex-1 max-w-3xl mx-auto w-full px-2 sm:px-4">
        {/* Header */}
        <header className="flex items-center justify-between py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (window.innerWidth < 768) {
                  setSidebarOpen(true);
                } else {
                  setShowSidebar(!showSidebar);
                }
              }}
              className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              aria-label="Toggle sidebar"
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            <div className="p-1.5 rounded-lg bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15">
              <MessageSquare className="w-4 h-4 text-primary" />
            </div>
            <h1 className="text-lg font-semibold text-foreground hidden sm:block">Chat Planner</h1>
          </div>
          <button
            onClick={handleNewChat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted hover:bg-accent border border-border rounded-lg transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            New Chat
          </button>
        </header>

        {/* Error Banner */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              role="alert"
              className="p-3 mt-2 rounded-xl bg-red-500/10 border border-red-500/20"
            >
              <p className="text-red-600 text-sm">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          role="log"
          aria-live="polite"
          aria-label="Chat messages"
          className="flex-1 overflow-y-auto py-4 space-y-4 relative md:px-4"
        >
          <ErrorBoundary
            fallback={
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
                Something went wrong rendering this conversation. Start a New Chat to continue.
              </div>
            }
          >
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              role="article"
              aria-label={msg.role === 'user' ? 'User message' : 'Assistant message'}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-primary/10 border border-primary/20 text-foreground'
                    : 'bg-card border border-border text-foreground/90 shadow-sm'
                }`}
                tabIndex={0}
              >
                {msg.role === 'assistant' ? (
                  <MarkdownRenderer content={msg.content} />
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                )}
                {msg.comparison && <ComparisonView data={msg.comparison} onSelect={handleSelectPlan} />}
                {msg.itinerary && <ItineraryCard itinerary={msg.itinerary} threadId={threadId ?? undefined} />}
              </div>
            </motion.div>
          ))}

          {/* Pending (offline-queued) messages */}
          {pendingMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex justify-end"
            >
              <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-muted/50 border border-border text-muted-foreground">
                <div className="flex items-center gap-1.5 mb-1">
                  <Clock className="w-3 h-3 animate-pulse" />
                  <span className="text-[10px] font-medium">Pending — will send when online</span>
                </div>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </motion.div>
          ))}

          {/* Streaming message */}
          {loading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex justify-start"
            >
              <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-card border border-border text-foreground/90 shadow-sm">
                {activeWorkers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {activeWorkers.map((tool) => (
                      <span
                        key={tool}
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 border border-primary/20 text-[10px] font-medium text-primary"
                      >
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {TOOL_ICONS[tool]}
                        {TOOL_LABELS[tool]}
                      </span>
                    ))}
                  </div>
                )}
                {streamingText ? (
                  <>
                    <MarkdownRenderer content={streamingText} />
                    <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-0.5" />
                  </>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {elapsed < 5 ? 'Thinking...' : elapsed < 15 ? `Thinking... ${elapsed}s` : `Still thinking... ${elapsed}s`}
                    </span>
                  </div>
                )}
                {streamingComparison && <ComparisonView data={streamingComparison} onSelect={handleSelectPlan} />}
                {streamingItinerary && <ItineraryCard itinerary={streamingItinerary} threadId={threadId ?? undefined} />}
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
          </ErrorBoundary>

          {/* Scroll to bottom button */}
          <AnimatePresence>
            {!isAtBottom && (messages.length > 4 || loading) && (
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                onClick={scrollToBottom}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 p-2 rounded-full bg-card border border-border shadow-lg hover:bg-accent transition-colors cursor-pointer z-10"
                aria-label="Scroll to latest message"
              >
                <ChevronDown className="w-4 h-4 text-foreground" />
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Input bar */}
        <div className="py-4 border-t border-border">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your dream trip..."
              rows={1}
              disabled={loading}
              aria-label="Message input"
              className="flex-1 bg-muted border border-border rounded-xl px-3 sm:px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none outline-none focus:border-primary/40 focus:bg-card transition-colors disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="p-3 bg-primary/10 hover:bg-primary/20 border border-primary/30 rounded-xl text-primary transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
            {loading && (
              <button
                onClick={() => abortRef.current?.abort()}
                className="p-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/25 rounded-xl text-red-600 transition-all cursor-pointer"
                aria-label="Stop generating"
              >
                <Square className="w-4 h-4" />
              </button>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground/40 mt-1.5 text-center">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
        </div>
      </div>
    </main>
  );
}
