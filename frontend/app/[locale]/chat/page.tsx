'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, RotateCcw, Globe, Search, ShieldAlert, ListChecks, Loader2, PanelLeft, ChevronDown, ChevronLeft, ChevronRight, Clock, Sparkles, Copy, Check, Pencil, X, Mic, Paperclip, FileText } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useLocale } from '@/lib/useLocale';
import { streamChat, cancelStream, regenerateStream, editStream } from '@/lib/chat-api';
import { listThreads, getThreadHistory, getBranches, deleteThread, updateThread, type ThreadMeta } from '@/lib/threads-api';
import { getSession, type SessionUser } from '@/lib/auth';
import { useOnlineStatus } from '@/lib/useOnlineStatus';
import { useThrottledValue } from '@/lib/useThrottledValue';
import { queueMessage, replayQueuedMessages, type QueuedMessage } from '@/lib/message-queue';
import ErrorBoundary from '@/components/ErrorBoundary';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import SuggestionPrompts from '@/components/SuggestionPrompts';
import CopyButton, { buildCopyContent } from '@/components/CopyButton';
import ItineraryCard from '@/components/ItineraryCard';
import OfflineBanner from '@/components/OfflineBanner';
import ThinkingBlock from '@/components/ThinkingBlock';
import ToolCallCard from '@/components/ToolCallCard';
import SubagentTimeline from '@/components/SubagentTimeline';
import ActivityPanel from '@/components/ActivityPanel';
import ComparisonView from './ComparisonView';
import FeedbackButtons from '@/components/FeedbackButtons';
import ThreadSidebar from './ThreadSidebar';
import VoiceWaveform from '@/components/VoiceWaveform';
import FilePreview from '@/components/FilePreview';
import { useVoiceInput } from '@/lib/useVoiceInput';
import { uploadFile, type UploadedFile } from '@/lib/upload-api';
import type { ChatMessage, ComparisonData, Itinerary, ActivityData, BranchInfo } from '@/lib/types';

const THREAD_STORAGE_KEY = 'voyagerai_chat_thread_id';

const TOOL_LABEL_KEYS: Record<string, string> = {
  researcher: 'researching',
  risk_detector: 'checkingRisks',
  constraint_analyzer: 'checkingConstraints',
  validator: 'validating',
  enricher: 'addingTips',
  cost_optimizer: 'optimizingBudget',
  multi_plan_generator: 'generatingPlans',
  quality_scorer: 'scoringQuality',
};

const TOOL_ICONS: Record<string, React.ReactNode> = {
  researcher: <Search className="w-3 h-3" />,
  risk_detector: <ShieldAlert className="w-3 h-3" />,
  constraint_analyzer: <ListChecks className="w-3 h-3" />,
  multi_plan_generator: <Globe className="w-3 h-3" />,
  quality_scorer: <ListChecks className="w-3 h-3" />,
};

export default function ChatPage() {
  const t = useTranslations('chat');
  const tStatus = useTranslations('status');
  const tCommon = useTranslations('common');
  const locale = useLocale();
  const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [streamingText, setStreamingText] = useState('');
  const [streamingItinerary, setStreamingItinerary] = useState<Itinerary | null>(null);
  const [streamingComparison, setStreamingComparison] = useState<ComparisonData | null>(null);
  const [streamingActivity, setStreamingActivity] = useState<ActivityData | null>(null);
  const [activeWorkers, setActiveWorkers] = useState<string[]>([]);
  const [progressMap, setProgressMap] = useState<Record<string, string>>({});
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
  const [currentUser, setCurrentUser] = useState<SessionUser | null>(null);
  const isOnline = useOnlineStatus();
  const [pendingMessages, setPendingMessages] = useState<QueuedMessage[]>([]);
  const [replaying, setReplaying] = useState(false);
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [activeBranchIndex, setActiveBranchIndex] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [reconnecting, setReconnecting] = useState<{ attempt: number; max: number } | null>(null);
  const lastSentMessageRef = useRef<{ message: string; attachments?: UploadedFile[] } | null>(null);
  const lastRegenerateRef = useRef(false);
  const lastEditRef = useRef<{ threadId: string; message: string } | null>(null);

  const throttledStreamingText = useThrottledValue(streamingText, loading || regenerating);

  const abortRef = useRef<AbortController | null>(null);
  const sendingRef = useRef(false);
  const sessionResetRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const streamingActivityRef = useRef<ActivityData | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSession().then(async (user) => {
      if (cancelled) return;
      if (!user) {
        // Retry once after a delay — backend may still be starting up
        await new Promise((r) => setTimeout(r, 1500));
        if (cancelled) return;
        user = await getSession();
      }
      if (!user) {
        window.location.href = '/login';
        return;
      }
      setCurrentUser(user);
      setAuthChecked(true);
      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    });
    return () => { cancelled = true; };
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 128)}px`;
    }
  }, [input]);

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
    setMessages([]);
    setThreadId(null);
    setBranches([]);
    setActiveBranchIndex(0);
    setEditingMessageId(null);
    setEditContent('');
    localStorage.removeItem(THREAD_STORAGE_KEY);
    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});
  };

  const handleSelectThread = async (selectedThreadId: string) => {
    if (selectedThreadId === threadId) return;

    abortRef.current?.abort();
    setLoadingHistory(true);
    setThreadId(selectedThreadId);
    setBranches([]);
    setActiveBranchIndex(0);
    setEditingMessageId(null);
    setEditContent('');
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
      activity: msg.activity,
    }));

    if (historyMessages.length === 0) {
      setMessages([]);
    } else {
      setMessages(historyMessages);
    }

    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});
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

  const handleTogglePin = async (threadIdToPin: string, pinned: boolean) => {
    const ok = await updateThread(threadIdToPin, pinned);
    if (ok) {
      setThreads((prev) => prev.map(t =>
        t.thread_id === threadIdToPin
          ? { ...t, pinned, pinned_at: pinned ? Date.now() / 1000 : 0 }
          : t
      ));
    }
  };

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    if (pendingAttachments.length + files.length > 3) {
      setUploadError(t('tooManyFiles'));
      return;
    }
    setUploading(true);
    setUploadError(null);
    for (const file of Array.from(files)) {
      if (file.size > 10 * 1024 * 1024) {
        setUploadError(t('fileTooLarge'));
        continue;
      }
      try {
        const uploaded = await uploadFile(file);
        setPendingAttachments(prev => [...prev, uploaded]);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : t('uploadFailed'));
      }
    }
    setUploading(false);
  };

  const handleSend = useCallback(async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
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
    setUploadError(null);
    setReconnecting(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      attachments: pendingAttachments.length > 0 ? pendingAttachments : undefined,
    };
    setMessages((prev) => [...prev, userMessage]);
    const sentAttachments = pendingAttachments;
    setPendingAttachments([]);

    lastSentMessageRef.current = { message: text, attachments: sentAttachments.length > 0 ? sentAttachments : undefined };

    // Optimistic thread title — immediately show in sidebar before AI response completes
    if (!threadId) {
      const optimisticThread: ThreadMeta = {
        thread_id: 'optimistic-' + Date.now(),
        summary: text.slice(0, 40),
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        status: 'busy',
        message_count: 1,
      };
      setThreads((prev) => [optimisticThread, ...prev]);
    }

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

    const updateActivity = (updater: (prev: ActivityData | null) => ActivityData) => {
      const next = updater(streamingActivityRef.current);
      streamingActivityRef.current = next;
      setStreamingActivity(next);
    };

    try {
      const newThreadId = await streamChat(
        { message: text, thread_id: threadId ?? undefined, locale, timezone: userTimezone, attachments: sentAttachments.length > 0 ? sentAttachments : undefined },
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
            if (!TOOL_LABEL_KEYS[tool]) return;
            setActiveWorkers((prev) =>
              status.status === 'running'
                ? prev.includes(tool) ? prev : [...prev, tool]
                : prev.filter((t) => t !== tool),
            );
          },
          onThinking: (text) => {
            updateActivity((prev) => ({
              thinking: [...(prev?.thinking ?? []), { text }],
              tool_calls: prev?.tool_calls ?? [],
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolStart: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: [...(prev?.tool_calls ?? []), {
                run_id: tool.run_id,
                name: tool.name,
                input: tool.input,
                status: 'running' as const,
                started_at: Date.now(),
                parent_run_id: tool.parent_run_id,
              }],
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolEnd: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: (prev?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, output: tool.output, status: 'done' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolError: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: (prev?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, error: tool.error, status: 'error' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onUsage: (usage) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: prev?.tool_calls ?? [],
              usage: [...(prev?.usage ?? []), usage],
              total_input_tokens: (prev?.total_input_tokens ?? 0) + usage.input_tokens,
              total_output_tokens: (prev?.total_output_tokens ?? 0) + usage.output_tokens,
            }));
          },
          onSubagentProgress: (data) => {
            setProgressMap((prev) => ({ ...prev, [data.run_id]: data.description }));
          },
          onReconnecting: (attempt, max) => {
            setReconnecting({ attempt, max });
          },
          onError: (msg) => {
            streamFailed = true;
            errorMessage = msg;
            setError(msg);
            setReconnecting(null);
          },
          onAbort: () => {
            aborted = true;
            setReconnecting(null);
          },
          onCancelled: () => {
            aborted = true;
            setReconnecting(null);
          },
          errorMessages: {
            serverResponse: (status, detail) => t('errorServerResponse', { status, detail }),
            responseBody: t('errorResponseBody'),
            parseFailed: t('errorParseFailed'),
            streamEnded: t('errorStreamEnded'),
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
              content: t('generationFailed', { error: errorMessage || 'unknown error' }),
            };
          } else if (aborted && accumulatedText) {
            updated[idx] = {
              ...updated[idx],
              content: accumulatedText,
              itinerary: accumulatedItinerary ?? undefined,
              comparison: accumulatedComparison ?? undefined,
              activity: streamingActivityRef.current ?? undefined,
              wasStopped: true,
            };
          } else if (aborted && !accumulatedText) {
            updated[idx] = { ...updated[idx], content: t('generationStopped') };
          } else {
            updated[idx] = {
              ...updated[idx],
              content: accumulatedText,
              itinerary: accumulatedItinerary ?? undefined,
              comparison: accumulatedComparison ?? undefined,
              activity: streamingActivityRef.current ?? undefined,
            };
          }
        }
        return updated;
      });

      setStreamingText('');
      setStreamingItinerary(null);
      setStreamingComparison(null);
      setStreamingActivity(null);
      streamingActivityRef.current = null;
      setReconnecting(null);

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
    setProgressMap({});
      sendingRef.current = false;
      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    }
  }, [input, loading, threadId, isOnline]);

  const handleRetry = useCallback(() => {
    if (!lastSentMessageRef.current || loading) return;
    setError(null);
    handleSend(lastSentMessageRef.current.message);
  }, [loading, handleSend]);

  const handleRegenerate = useCallback(async () => {
    if (!threadId || loading || regenerating) return;

    setRegenerating(true);
    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedText = '';
    let accumulatedItinerary: Itinerary | null = null;
    let accumulatedComparison: ComparisonData | null = null;
    let streamFailed = false;
    let errorMessage = '';
    let aborted = false;

    try {
      await regenerateStream(
        { thread_id: threadId, locale, timezone: userTimezone },
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
          },
          onStatus: (status) => {
            const tool = status.tool;
            if (!TOOL_LABEL_KEYS[tool]) return;
            setActiveWorkers((prev) =>
              status.status === 'running'
                ? prev.includes(tool) ? prev : [...prev, tool]
                : prev.filter((t) => t !== tool),
            );
          },
          onThinking: (text) => {
            const next = {
              thinking: [...(streamingActivityRef.current?.thinking ?? []), { text }],
              tool_calls: streamingActivityRef.current?.tool_calls ?? [],
              usage: streamingActivityRef.current?.usage ?? [],
              total_input_tokens: streamingActivityRef.current?.total_input_tokens ?? 0,
              total_output_tokens: streamingActivityRef.current?.total_output_tokens ?? 0,
            };
            streamingActivityRef.current = next;
            setStreamingActivity(next);
          },
          onToolStart: (tool) => {
            const next = {
              thinking: streamingActivityRef.current?.thinking ?? [],
              tool_calls: [...(streamingActivityRef.current?.tool_calls ?? []), {
                run_id: tool.run_id,
                name: tool.name,
                input: tool.input,
                status: 'running' as const,
                started_at: Date.now(),
                parent_run_id: tool.parent_run_id,
              }],
              usage: streamingActivityRef.current?.usage ?? [],
              total_input_tokens: streamingActivityRef.current?.total_input_tokens ?? 0,
              total_output_tokens: streamingActivityRef.current?.total_output_tokens ?? 0,
            };
            streamingActivityRef.current = next;
            setStreamingActivity(next);
          },
          onToolEnd: (tool) => {
            const next = {
              thinking: streamingActivityRef.current?.thinking ?? [],
              tool_calls: (streamingActivityRef.current?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, output: tool.output, status: 'done' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: streamingActivityRef.current?.usage ?? [],
              total_input_tokens: streamingActivityRef.current?.total_input_tokens ?? 0,
              total_output_tokens: streamingActivityRef.current?.total_output_tokens ?? 0,
            };
            streamingActivityRef.current = next;
            setStreamingActivity(next);
          },
          onToolError: (tool) => {
            const next = {
              thinking: streamingActivityRef.current?.thinking ?? [],
              tool_calls: (streamingActivityRef.current?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, error: tool.error, status: 'error' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: streamingActivityRef.current?.usage ?? [],
              total_input_tokens: streamingActivityRef.current?.total_input_tokens ?? 0,
              total_output_tokens: streamingActivityRef.current?.total_output_tokens ?? 0,
            };
            streamingActivityRef.current = next;
            setStreamingActivity(next);
          },
          onUsage: (usage) => {
            const next = {
              thinking: streamingActivityRef.current?.thinking ?? [],
              tool_calls: streamingActivityRef.current?.tool_calls ?? [],
              usage: [...(streamingActivityRef.current?.usage ?? []), usage],
              total_input_tokens: (streamingActivityRef.current?.total_input_tokens ?? 0) + usage.input_tokens,
              total_output_tokens: (streamingActivityRef.current?.total_output_tokens ?? 0) + usage.output_tokens,
            };
            streamingActivityRef.current = next;
            setStreamingActivity(next);
          },
          onSubagentProgress: (data) => {
            setProgressMap((prev) => ({ ...prev, [data.run_id]: data.description }));
          },
          onReconnecting: (attempt, max) => {
            setReconnecting({ attempt, max });
          },
          onError: (msg) => {
            streamFailed = true;
            errorMessage = msg;
            setError(msg);
            setReconnecting(null);
          },
          onAbort: () => {
            aborted = true;
            setReconnecting(null);
          },
          onCancelled: () => {
            aborted = true;
            setReconnecting(null);
          },
          onDone: () => {},
        },
      );
    } finally {
      // Replace the last assistant message with the regenerated response
      setMessages((prev) => {
        const updated = [...prev];
        // Find the last assistant message
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant') {
            if (streamFailed) {
              updated[i] = {
                ...updated[i],
                content: accumulatedText || (errorMessage || t('generationFailed', { error: '' })),
              };
            } else if (aborted) {
              updated[i] = {
                ...updated[i],
                content: accumulatedText,
                wasStopped: true,
              };
            } else {
              updated[i] = {
                ...updated[i],
                content: accumulatedText,
                itinerary: accumulatedItinerary ?? undefined,
                comparison: accumulatedComparison ?? undefined,
                activity: streamingActivityRef.current ?? undefined,
              };
            }
            break;
          }
        }
        return updated;
      });

      setRegenerating(false);
      setLoading(false);
      abortRef.current = null;
      setActiveWorkers([]);
    setProgressMap({});
      setStreamingText('');
      setStreamingItinerary(null);
      setStreamingComparison(null);
      setStreamingActivity(null);
      streamingActivityRef.current = null;

      // Fetch branches after regeneration
      if (threadId && !aborted) {
        const branchList = await getBranches(threadId);
        setBranches(branchList);
        const currentIdx = branchList.findIndex((b) => b.is_current);
        setActiveBranchIndex(currentIdx >= 0 ? currentIdx : 0);
      }

      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    }
  }, [threadId, loading, regenerating, locale, t]);

  const handleSwitchBranch = useCallback(async (checkpointId: string, index: number) => {
    if (!threadId) return;

    setLoadingHistory(true);
    try {
      const history = await getThreadHistory(threadId, checkpointId);
      const historyMessages: ChatMessage[] = history.map((msg, i) => ({
        id: `branch-${i}`,
        role: msg.role,
        content: msg.content,
        itinerary: msg.itinerary,
        comparison: msg.comparison,
        activity: msg.activity,
      }));

      setMessages(historyMessages);
      setActiveBranchIndex(index);
      setBranches((prev) => prev.map((b, i) => ({
        ...b,
        is_current: i === index,
      })));
    } finally {
      setLoadingHistory(false);
    }
  }, [threadId]);

  const handleEditSave = useCallback(async () => {
    if (!threadId || !editingMessageId || !editContent.trim()) return;

    setEditingMessageId(null);
    setLoading(true);
    setError(null);
    setStreamingText('');
    setStreamingItinerary(null);
    setStreamingComparison(null);
    setStreamingActivity(null);
    streamingActivityRef.current = null;
    setActiveWorkers([]);
    setProgressMap({});

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulatedText = '';
    let accumulatedItinerary: Itinerary | null = null;
    let accumulatedComparison: ComparisonData | null = null;
    let streamFailed = false;
    let errorMessage = '';
    let aborted = false;

    const updateActivity = (updater: (prev: ActivityData | null) => ActivityData) => {
      const next = updater(streamingActivityRef.current);
      streamingActivityRef.current = next;
      setStreamingActivity(next);
    };

    try {
      await editStream(
        { thread_id: threadId, message: editContent.trim(), locale, timezone: userTimezone },
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
          onThreadId: () => {},
          onStatus: (status) => {
            const tool = status.tool;
            if (!TOOL_LABEL_KEYS[tool]) return;
            setActiveWorkers((prev) =>
              status.status === 'running'
                ? prev.includes(tool) ? prev : [...prev, tool]
                : prev.filter((t) => t !== tool),
            );
          },
          onThinking: (text) => {
            updateActivity((prev) => ({
              thinking: [...(prev?.thinking ?? []), { text }],
              tool_calls: prev?.tool_calls ?? [],
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolStart: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: [...(prev?.tool_calls ?? []), {
                run_id: tool.run_id,
                name: tool.name,
                input: tool.input,
                status: 'running' as const,
                started_at: Date.now(),
                parent_run_id: tool.parent_run_id,
              }],
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolEnd: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: (prev?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, output: tool.output, status: 'done' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onToolError: (tool) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: (prev?.tool_calls ?? []).map((tc) =>
                tc.run_id === tool.run_id
                  ? { ...tc, error: tool.error, status: 'error' as const, ended_at: Date.now() }
                  : tc
              ),
              usage: prev?.usage ?? [],
              total_input_tokens: prev?.total_input_tokens ?? 0,
              total_output_tokens: prev?.total_output_tokens ?? 0,
            }));
          },
          onUsage: (usage) => {
            updateActivity((prev) => ({
              thinking: prev?.thinking ?? [],
              tool_calls: prev?.tool_calls ?? [],
              usage: [...(prev?.usage ?? []), usage],
              total_input_tokens: (prev?.total_input_tokens ?? 0) + usage.input_tokens,
              total_output_tokens: (prev?.total_output_tokens ?? 0) + usage.output_tokens,
            }));
          },
          onSubagentProgress: (data) => {
            setProgressMap((prev) => ({ ...prev, [data.run_id]: data.description }));
          },
          onReconnecting: (attempt, max) => {
            setReconnecting({ attempt, max });
          },
          onError: (msg) => {
            streamFailed = true;
            errorMessage = msg;
            setError(msg);
            setReconnecting(null);
          },
          onAbort: () => { aborted = true; setReconnecting(null); },
          onCancelled: () => { aborted = true; setReconnecting(null); },
          onDone: () => {},
        },
      );
    } finally {
      // Update the user message content and replace the assistant response
      setMessages((prev) => {
        const updated = [...prev];
        // Update the last user message with edited content
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'user') {
            updated[i] = { ...updated[i], content: editContent.trim() };
            break;
          }
        }
        // Replace the last assistant message
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant') {
            if (streamFailed) {
              updated[i] = {
                ...updated[i],
                content: accumulatedText || t('generationFailed', { error: errorMessage || '' }),
              };
            } else if (aborted) {
              updated[i] = {
                ...updated[i],
                content: accumulatedText,
                wasStopped: true,
              };
            } else {
              updated[i] = {
                ...updated[i],
                content: accumulatedText,
                itinerary: accumulatedItinerary ?? undefined,
                comparison: accumulatedComparison ?? undefined,
                activity: streamingActivityRef.current ?? undefined,
              };
            }
            break;
          }
        }
        return updated;
      });

      setLoading(false);
      abortRef.current = null;
      setActiveWorkers([]);
    setProgressMap({});
      setStreamingText('');
      setStreamingItinerary(null);
      setStreamingComparison(null);
      setStreamingActivity(null);
      streamingActivityRef.current = null;

      // Fetch branches after edit
      if (threadId && !aborted) {
        const branchList = await getBranches(threadId);
        setBranches(branchList);
        const currentIdx = branchList.findIndex((b) => b.is_current);
        setActiveBranchIndex(currentIdx >= 0 ? currentIdx : 0);
      }

      listThreads().then((res) => {
        setThreads(res.threads);
        setHasMoreThreads(res.has_more);
      });
    }
  }, [threadId, editingMessageId, editContent, locale, t]);

  const handleEditCancel = useCallback(() => {
    setEditingMessageId(null);
    setEditContent('');
  }, []);

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
            { message: msg.content, thread_id: msg.thread_id ?? undefined, locale, timezone: userTimezone },
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
                if (!TOOL_LABEL_KEYS[tool]) return;
                setActiveWorkers((prev) =>
                  status.status === 'running'
                    ? prev.includes(tool) ? prev : [...prev, tool]
                    : prev.filter((t) => t !== tool),
                );
              },
              onThinking: (text) => {
                const prev = streamingActivityRef.current;
                const next = { thinking: [...(prev?.thinking ?? []), { text }], tool_calls: prev?.tool_calls ?? [], usage: prev?.usage ?? [], total_input_tokens: prev?.total_input_tokens ?? 0, total_output_tokens: prev?.total_output_tokens ?? 0 };
                streamingActivityRef.current = next;
                setStreamingActivity(next);
              },
              onToolStart: (tool) => {
                const prev = streamingActivityRef.current;
                const next = { thinking: prev?.thinking ?? [], tool_calls: [...(prev?.tool_calls ?? []), { run_id: tool.run_id, name: tool.name, input: tool.input, status: 'running' as const, started_at: Date.now(), parent_run_id: tool.parent_run_id }], usage: prev?.usage ?? [], total_input_tokens: prev?.total_input_tokens ?? 0, total_output_tokens: prev?.total_output_tokens ?? 0 };
                streamingActivityRef.current = next;
                setStreamingActivity(next);
              },
              onToolEnd: (tool) => {
                const prev = streamingActivityRef.current;
                const next = { thinking: prev?.thinking ?? [], tool_calls: (prev?.tool_calls ?? []).map((tc) => tc.run_id === tool.run_id ? { ...tc, output: tool.output, status: 'done' as const, ended_at: Date.now() } : tc), usage: prev?.usage ?? [], total_input_tokens: prev?.total_input_tokens ?? 0, total_output_tokens: prev?.total_output_tokens ?? 0 };
                streamingActivityRef.current = next;
                setStreamingActivity(next);
              },
              onToolError: (tool) => {
                const prev = streamingActivityRef.current;
                const next = { thinking: prev?.thinking ?? [], tool_calls: (prev?.tool_calls ?? []).map((tc) => tc.run_id === tool.run_id ? { ...tc, error: tool.error, status: 'error' as const, ended_at: Date.now() } : tc), usage: prev?.usage ?? [], total_input_tokens: prev?.total_input_tokens ?? 0, total_output_tokens: prev?.total_output_tokens ?? 0 };
                streamingActivityRef.current = next;
                setStreamingActivity(next);
              },
              onUsage: (usage) => {
                const prev = streamingActivityRef.current;
                const next = { thinking: prev?.thinking ?? [], tool_calls: prev?.tool_calls ?? [], usage: [...(prev?.usage ?? []), usage], total_input_tokens: (prev?.total_input_tokens ?? 0) + usage.input_tokens, total_output_tokens: (prev?.total_output_tokens ?? 0) + usage.output_tokens };
                streamingActivityRef.current = next;
                setStreamingActivity(next);
              },
              onSubagentProgress: (data) => {
                setProgressMap((prev) => ({ ...prev, [data.run_id]: data.description }));
              },
              onError: (msg) => {
                streamFailed = true;
                errorMessage = msg;
                setError(msg);
              },
              errorMessages: {
                serverResponse: (status, detail) => t('errorServerResponse', { status, detail }),
                responseBody: t('errorResponseBody'),
                parseFailed: t('errorParseFailed'),
                streamEnded: t('errorStreamEnded'),
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
                  content: t('generationFailed', { error: errorMessage || 'unknown error' }),
                };
              } else {
                updated[idx] = {
                  ...updated[idx],
                  content: accumulatedText,
                  itinerary: accumulatedItinerary ?? undefined,
                  comparison: accumulatedComparison ?? undefined,
                  activity: streamingActivityRef.current ?? undefined,
                };
              }
            }
            return updated;
          });

          setStreamingText('');
          setStreamingItinerary(null);
          setStreamingComparison(null);
          setStreamingActivity(null);
          streamingActivityRef.current = null;
          setLoading(false);
          setActiveWorkers([]);
    setProgressMap({});
          return true;
        } catch {
          setLoading(false);
          setActiveWorkers([]);
    setProgressMap({});
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
    setInput(t('selectPlan', { tier }));
    inputRef.current?.focus();
  }, [t]);

  const { isSupported: voiceSupported, isRecording: isRecordingVoice, start: startRecording, stop: stopRecording, error: voiceError } = useVoiceInput({
    locale,
    onTranscript: (text) => {
      setInput(text);
      inputRef.current?.focus();
    },
  });

  useEffect(() => {
    if (!isRecordingVoice) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        stopRecording();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isRecordingVoice, stopRecording]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isRecordingVoice) return;
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!authChecked) {
    return (
      <main className="h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </main>
    );
  }

  return (
    <main className="h-screen flex flex-col overflow-hidden bg-background">
      <OfflineBanner replaying={replaying} />

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
                onTogglePin={handleTogglePin}
                onClose={() => setShowSidebar(false)}
                user={currentUser}
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
              aria-label={t('conversationHistory')}
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
                  onTogglePin={handleTogglePin}
                  onClose={() => setSidebarOpen(false)}
                  user={currentUser}
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

        <div className="flex flex-col flex-1 min-w-0 relative">
        {/* Subtle background tint */}
        <div className="absolute inset-0 bg-gradient-to-b from-primary/[0.015] via-transparent to-primary/[0.01] pointer-events-none" />

        {messages.length === 0 && !loading ? (
          <SuggestionPrompts
            onSend={handleSend}
            input={input}
            setInput={setInput}
            inputRef={inputRef}
            handleKeyDown={handleKeyDown}
            t={t}
          />
        ) : (
          /* ─── Normal chat layout ─── */
          <>
        {/* Header */}
        <header className="flex items-center justify-between py-3 px-4 border-b border-border/50 relative">
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
              aria-label={t('toggleSidebar')}
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            {!showSidebar && (
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-gradient-to-br from-indigo-500/10 to-violet-500/10 border border-indigo-500/15">
                  <Sparkles className="w-3.5 h-3.5 text-primary" />
                </div>
                <span className="text-sm font-semibold text-foreground">{t('title')}</span>
              </div>
            )}
          </div>
          <button
            onClick={handleNewChat}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted hover:bg-accent border border-border rounded-lg transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            {t('newChat')}
          </button>
        </header>

        {/* Reconnecting Banner */}
        <AnimatePresence>
          {reconnecting && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="p-3 mt-2 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center gap-2"
            >
              <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
              <p className="text-amber-600 text-sm">
                {t('reconnecting', { attempt: reconnecting.attempt, max: reconnecting.max })}
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error Banner */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              role="alert"
              className="p-3 mt-2 rounded-xl bg-red-500/10 border border-red-500/20 relative flex items-center justify-between gap-3"
            >
              <p className="text-red-600 text-sm">{error}</p>
              {lastSentMessageRef.current && (
                <button
                  onClick={handleRetry}
                  className="text-sm font-medium text-red-600 hover:text-red-700 underline shrink-0 cursor-pointer"
                >
                  {t('retry')}
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false); }}
          onDrop={(e) => {
            e.preventDefault(); e.stopPropagation();
            setIsDragging(false);
            if (e.dataTransfer.types.includes('Files') && e.dataTransfer.files.length > 0) {
              handleFileSelect(e.dataTransfer.files);
            }
          }}
          role="log"
          aria-live="polite"
          aria-label={t('chatMessages')}
          className="flex-1 overflow-y-auto py-6 relative"
        >
          {isDragging && (
            <div className="absolute inset-0 z-10 bg-primary/5 border-2 border-dashed border-primary/30 rounded-lg flex items-center justify-center pointer-events-none">
              <p className="text-sm text-primary font-medium">{t('dropFilesHere')}</p>
            </div>
          )}
          <div className="max-w-3xl mx-auto w-full px-4 space-y-6">
          <ErrorBoundary
            errorTitle={tCommon('errorTitle')}
            errorDescription={tCommon('errorDescription')}
            tryAgain={tCommon('tryAgain')}
            fallback={
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
                {t('errorRendering')}
              </div>
            }
          >
          {messages.map((msg, msgIndex) => {
            const isLastAssistant = msg.role === 'assistant' && msgIndex === messages.length - 1;
            const isLastUser = msg.role === 'user' && msgIndex === messages.length - 1;
            const prevUserMsg = msgIndex > 0 && messages[msgIndex - 1].role === 'user' ? messages[msgIndex - 1] : null;
            return (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              role="article"
              aria-label={msg.role === 'user' ? t('userMessage') : t('assistantMessage')}
            >
              {msg.role === 'user' ? (
                editingMessageId === msg.id ? (
                  <div className="max-w-[75%] w-full">
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      autoFocus
                      rows={2}
                      className="w-full rounded-2xl px-4 py-3 bg-primary/10 border border-primary/30 text-foreground text-sm resize-none outline-none focus:ring-1 focus:ring-primary/40"
                      aria-label={t('editing')}
                    />
                    <div className="flex items-center gap-2 mt-2 justify-end">
                      <button
                        onClick={handleEditCancel}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted hover:bg-accent border border-border rounded-lg transition-colors cursor-pointer"
                      >
                        <X className="w-3.5 h-3.5" />
                        {t('cancelEdit')}
                      </button>
                      <button
                        onClick={handleEditSave}
                        disabled={!editContent.trim() || loading}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Check className="w-3.5 h-3.5" />
                        {t('saveEdit')}
                      </button>
                    </div>
                  </div>
                ) : (
                <div
                  className="max-w-[75%] rounded-2xl px-4 py-3 bg-primary/10 border border-primary/15 text-foreground group relative"
                  tabIndex={0}
                >
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {msg.attachments.map(att => (
                        att.content_type.startsWith('image/') ? (
                          <img
                            key={att.file_id}
                            src={att.data_url}
                            alt={att.filename}
                            className="max-w-[200px] max-h-[200px] rounded-lg object-cover"
                          />
                        ) : (
                          <div key={att.file_id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted text-xs">
                            <FileText className="w-4 h-4 shrink-0" />
                            <span className="truncate max-w-[150px]">{att.filename}</span>
                          </div>
                        )
                      ))}
                    </div>
                  )}
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  {isLastUser && !loading && !regenerating && (
                    <button
                      onClick={() => {
                        setEditingMessageId(msg.id);
                        setEditContent(msg.content);
                      }}
                      className="absolute -bottom-7 right-0 p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
                      aria-label={t('edit')}
                      title={t('edit')}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                )
              ) : (
                <div className="w-full group" tabIndex={0}>
                  <div className="px-1 py-1">
                    <ActivityPanel
                      activity={msg.activity ?? null}
                      activeWorkers={[]}
                      isStreaming={false}
                      hasText={!!msg.content}
                    />
                    <MarkdownRenderer content={msg.content} />
                    {msg.wasStopped && (
                      <span className="inline-flex items-center gap-1 mt-1 text-[10px] text-muted-foreground/60">
                        <Square className="w-2.5 h-2.5 fill-current" />
                        {t('stopped')}
                      </span>
                    )}
                    {msg.comparison && <ComparisonView data={msg.comparison} onSelect={handleSelectPlan} />}
                    {msg.itinerary && <ItineraryCard itinerary={msg.itinerary} threadId={threadId ?? undefined} />}
                  </div>
                  {/* Copy + Regenerate + Branch navigation buttons */}
                  {msg.content && (
                    <div className="flex items-center gap-1 px-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <CopyButton content={buildCopyContent(msg.content, msg.itinerary, msg.comparison)} />
                      <FeedbackButtons threadId={threadId ?? ''} messageId={msg.id} />
                      {isLastAssistant && prevUserMsg && (
                        <>
                          <button
                            onClick={() => handleRegenerate()}
                            disabled={regenerating}
                            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            aria-label={regenerating ? t('regenerating') : t('regenerate')}
                            title={regenerating ? t('regenerating') : t('regenerate')}
                          >
                            {regenerating ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <RotateCcw className="w-3.5 h-3.5" />
                            )}
                          </button>
                          {branches.length > 1 && (
                            <div className="flex items-center gap-0.5 ml-1">
                              <button
                                onClick={() => {
                                  const prevIdx = activeBranchIndex > 0 ? activeBranchIndex - 1 : branches.length - 1;
                                  handleSwitchBranch(branches[prevIdx].checkpoint_id, prevIdx);
                                }}
                                disabled={loadingHistory}
                                className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50"
                                aria-label={t('previousBranch')}
                                title={t('previousBranch')}
                              >
                                <ChevronLeft className="w-3.5 h-3.5" />
                              </button>
                              <span className="text-[10px] text-muted-foreground tabular-nums px-0.5">
                                {activeBranchIndex + 1}/{branches.length}
                              </span>
                              <button
                                onClick={() => {
                                  const nextIdx = activeBranchIndex < branches.length - 1 ? activeBranchIndex + 1 : 0;
                                  handleSwitchBranch(branches[nextIdx].checkpoint_id, nextIdx);
                                }}
                                disabled={loadingHistory}
                                className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50"
                                aria-label={t('nextBranch')}
                                title={t('nextBranch')}
                              >
                                <ChevronRight className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </motion.div>
            );
          })}

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
                  <span className="text-[10px] font-medium">{t('pending')}</span>
                </div>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </motion.div>
          ))}

          {/* Streaming message */}
          {(loading || regenerating) && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex justify-start"
            >
              <div className="w-full px-1 py-1">
                <ActivityPanel
                  activity={streamingActivity}
                  activeWorkers={activeWorkers}
                  isStreaming={loading || regenerating}
                  hasText={!!throttledStreamingText}
                  progressMap={progressMap}
                  workerIcons={TOOL_ICONS}
                  workerLabels={Object.fromEntries(
                    Object.entries(TOOL_LABEL_KEYS).map(([k, v]) => [k, tStatus(v)]),
                  )}
                />
                {throttledStreamingText ? (
                  <>
                    <MarkdownRenderer content={throttledStreamingText} streaming={true} />
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
                      {elapsed < 5 ? t('thinking') : elapsed < 15 ? t('thinkingSeconds', { seconds: elapsed }) : t('stillThinkingSeconds', { seconds: elapsed })}
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
          </div>

          {/* Scroll to bottom button */}
          <AnimatePresence>
            {!isAtBottom && (messages.length > 4 || loading) && (
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                onClick={scrollToBottom}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 p-2 rounded-full bg-card border border-border shadow-lg hover:bg-accent transition-colors cursor-pointer z-10"
                aria-label={t('scrollToLatest')}
              >
                <ChevronDown className="w-4 h-4 text-foreground" />
              </motion.button>
            )}
          </AnimatePresence>
        </div>

        {/* Input bar */}
        <div className="px-4 pb-3 pt-1 relative">
          <div className="max-w-3xl mx-auto w-full">
            {pendingAttachments.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2 px-1">
                {pendingAttachments.map(att => (
                  <FilePreview
                    key={att.file_id}
                    file={att}
                    onRemove={() => setPendingAttachments(prev => prev.filter(f => f.file_id !== att.file_id))}
                  />
                ))}
              </div>
            )}
            {uploadError && (
              <p className="text-xs text-destructive mb-2 px-1">{uploadError}</p>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf"
              multiple
              className="hidden"
              onChange={(e) => {
                handleFileSelect(e.target.files);
                e.target.value = '';
              }}
            />
            <div className="flex items-center gap-2 rounded-2xl border border-border bg-card shadow-sm px-4 py-3 focus-within:border-primary/40 focus-within:shadow-md transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isRecordingVoice ? t('listening') : t('placeholder')}
                rows={1}
                disabled={loading || regenerating || isRecordingVoice}
                aria-label={t('messageInput')}
                className="flex-1 bg-transparent border-0 text-sm text-foreground placeholder:text-muted-foreground/50 resize-none outline-none focus:ring-0 transition-colors disabled:opacity-50 max-h-32 leading-6"
              />
              {isRecordingVoice && <VoiceWaveform isActive={isRecordingVoice} />}
              {uploading && (
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground shrink-0" />
              )}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={loading || regenerating || isRecordingVoice || uploading || pendingAttachments.length >= 3}
                className="shrink-0 p-2 rounded-lg bg-muted hover:bg-accent text-foreground transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                aria-label={t('attachFile')}
              >
                <Paperclip className="w-4 h-4" />
              </button>
              {(loading || regenerating) && (
                <button
                  onClick={() => {
                    cancelStream(threadId ?? '');
                    abortRef.current?.abort();
                  }}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-muted hover:bg-accent border border-border text-foreground text-xs font-medium transition-all cursor-pointer"
                  aria-label={t('stop')}
                >
                  <Square className="w-3 h-3 fill-current" />
                  {t('stop')}
                </button>
              )}
              {voiceSupported && (
                <button
                  onClick={() => isRecordingVoice ? stopRecording() : startRecording()}
                  disabled={loading || regenerating}
                  className={`shrink-0 p-2 rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer ${
                    isRecordingVoice
                      ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse'
                      : 'bg-muted hover:bg-accent text-foreground'
                  }`}
                  aria-label={isRecordingVoice ? t('stopRecording') : t('voiceInput')}
                >
                  {isRecordingVoice ? (
                    <Square className="w-4 h-4 fill-current" />
                  ) : (
                    <Mic className="w-4 h-4" />
                  )}
                </button>
              )}
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading || isRecordingVoice}
                className="shrink-0 p-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                aria-label={t('send')}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-[10px] text-muted-foreground/40 mt-2 text-center">
              {t('enterToSend')}
            </p>
          </div>
        </div>
          </>
        )}
        </div>
      </div>
    </main>
  );
}
