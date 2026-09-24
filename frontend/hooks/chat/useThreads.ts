'use client';

import { useCallback, useState } from 'react';
import type React from 'react';
import { deleteThread, getThreadHistory, listThreads, updateThread, type ThreadMeta } from '@/lib/threads-api';
import { stripStructuredTags } from '@/lib/utils';
import type { BranchInfo, ChatMessage } from '@/lib/types';

export const THREAD_STORAGE_KEY = 'voyagerai_chat_thread_id';

export function mergeThreads(prev: ThreadMeta[], next: ThreadMeta[]): ThreadMeta[] {
  const map = new Map(prev.map((t) => [t.thread_id, t]));
  for (const t of next) map.set(t.thread_id, t);
  return [...map.values()].sort((a, b) => (b.pinned_at ?? 0) - (a.pinned_at ?? 0) || b.updated_at - a.updated_at);
}

interface ThreadDeps {
  threadId: string | null;
  setThreadId: (id: string | null) => void;
  abortRef: React.MutableRefObject<AbortController | null>;
  sessionResetRef: React.MutableRefObject<boolean>;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setBranches: (b: BranchInfo[]) => void;
  setActiveBranchIndex: (i: number) => void;
  setEditingMessageId: (id: string | null) => void;
  setEditContent: (c: string) => void;
  setError: (e: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  resetStreamAccumulators: () => void;
  resetGenerationUI: () => void;
}

/**
 * Thread list state + sidebar actions: select/delete/pin/load-more/new-chat.
 * Extracted from the chat page — no behavior change.
 */
export function useThreads(deps: ThreadDeps) {
  const {
    threadId, setThreadId, abortRef, sessionResetRef, setMessages,
    setBranches, setActiveBranchIndex, setEditingMessageId, setEditContent,
    setError, setSidebarOpen, resetStreamAccumulators, resetGenerationUI,
  } = deps;

  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [hasMoreThreads, setHasMoreThreads] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const handleNewChat = useCallback(() => {
    abortRef.current?.abort();
    sessionResetRef.current = true;
    setSidebarOpen(false);
    setMessages([]);
    setThreadId(null);
    setBranches([]);
    setActiveBranchIndex(0);
    setEditingMessageId(null);
    setEditContent('');
    try {
      localStorage.removeItem(THREAD_STORAGE_KEY);
    } catch {
      // storage unavailable
    }
    setError(null);
    resetStreamAccumulators();
    resetGenerationUI();
  }, [abortRef, sessionResetRef, setSidebarOpen, setMessages, setThreadId, setBranches,
      setActiveBranchIndex, setEditingMessageId, setEditContent, setError,
      resetStreamAccumulators, resetGenerationUI]);

  const handleSelectThread = useCallback(async (selectedThreadId: string) => {
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
      content: stripStructuredTags(msg.content),
      itinerary: msg.itinerary,
      comparison: msg.comparison,
      clarify: msg.clarify,
      activity: msg.activity,
      images: msg.images,
      charts: msg.charts,
    }));

    setMessages(historyMessages);
    setError(null);
    resetStreamAccumulators();
    setLoadingHistory(false);
  }, [threadId, abortRef, setThreadId, setBranches, setActiveBranchIndex,
      setEditingMessageId, setEditContent, setSidebarOpen, setMessages, setError,
      resetStreamAccumulators]);

  const handleDeleteThread = useCallback(async (threadIdToDelete: string) => {
    const ok = await deleteThread(threadIdToDelete);
    if (ok) {
      setThreads((prev) => prev.filter((t) => t.thread_id !== threadIdToDelete));
      if (threadIdToDelete === threadId) {
        handleNewChat();
      }
    }
  }, [threadId, handleNewChat]);

  const handleTogglePin = useCallback(async (threadIdToPin: string, pinned: boolean) => {
    const ok = await updateThread(threadIdToPin, pinned);
    if (ok) {
      setThreads((prev) => prev.map(t =>
        t.thread_id === threadIdToPin
          ? { ...t, pinned, pinned_at: pinned ? Date.now() / 1000 : 0 }
          : t
      ));
    }
  }, []);

  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true);
    const res = await listThreads(threads.length);
    setThreads((prev) => [...prev, ...res.threads]);
    setHasMoreThreads(res.has_more);
    setLoadingMore(false);
  }, [threads.length]);

  const refreshThreads = useCallback(async () => {
    const res = await listThreads();
    setThreads((prev) => mergeThreads(prev, res.threads));
    setHasMoreThreads(res.has_more);
  }, []);

  return {
    threads, setThreads,
    hasMoreThreads, setHasMoreThreads,
    loadingMore, loadingHistory, setLoadingHistory,
    handleNewChat, handleSelectThread, handleDeleteThread, handleTogglePin,
    handleLoadMore, refreshThreads,
  };
}
