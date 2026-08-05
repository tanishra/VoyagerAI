'use client';

import { useState } from 'react';
import { Plus, Trash2, MessageSquare, Loader2, ChevronDown } from 'lucide-react';
import type { ThreadMeta } from '@/lib/threads-api';

function formatRelativeTime(timestamp: number): string {
  const now = Date.now() / 1000;
  const diff = now - timestamp;

  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(timestamp * 1000).toLocaleDateString();
}

const STATUS_COLORS: Record<string, string> = {
  idle: 'bg-green-500',
  busy: 'bg-blue-500 animate-pulse',
  error: 'bg-red-500',
  interrupted: 'bg-amber-500',
};

interface ThreadSidebarProps {
  threads: ThreadMeta[];
  activeThreadId: string | null;
  loadingHistory: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onSelect: (threadId: string) => void;
  onDelete: (threadId: string) => void;
  onNewChat: () => void;
  onLoadMore: () => void;
}

export default function ThreadSidebar({
  threads,
  activeThreadId,
  loadingHistory,
  hasMore,
  loadingMore,
  onSelect,
  onDelete,
  onNewChat,
  onLoadMore,
}: ThreadSidebarProps) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handleDelete = (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    if (confirmDelete === threadId) {
      onDelete(threadId);
      setConfirmDelete(null);
    } else {
      setConfirmDelete(threadId);
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  };

  return (
    <div className="w-[260px] shrink-0 border-r border-border bg-card flex flex-col h-full">
      {/* New Chat button */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewChat}
          className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 border border-primary/20 text-primary text-sm font-medium transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <MessageSquare className="w-8 h-8 text-muted-foreground/30 mb-2" />
            <p className="text-sm text-muted-foreground">
              No conversations yet. Start chatting!
            </p>
          </div>
        ) : (
          <>
            {threads.map((thread) => {
              const isActive = thread.thread_id === activeThreadId;
              const isConfirming = confirmDelete === thread.thread_id;
              const statusColor = STATUS_COLORS[thread.status] || 'bg-muted-foreground/30';
              return (
                <div
                  key={thread.thread_id}
                  onClick={() => onSelect(thread.thread_id)}
                  className={`group relative px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
                    isActive
                      ? 'border-l-2 border-primary bg-primary/5'
                      : 'hover:bg-muted border-l-2 border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusColor}`} />
                        <p className={`text-sm truncate ${isActive ? 'text-foreground font-medium' : 'text-foreground/80'}`}>
                          {thread.summary || 'Untitled conversation'}
                        </p>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5 ml-3">
                        {formatRelativeTime(thread.updated_at)}
                        {thread.message_count > 0 && ` · ${thread.message_count} msgs`}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, thread.thread_id)}
                      className={`shrink-0 p-1 rounded transition-all cursor-pointer ${
                        isConfirming
                          ? 'text-red-600 bg-red-500/10 opacity-100'
                          : 'text-muted-foreground hover:text-red-600 opacity-0 group-hover:opacity-100'
                      }`}
                      aria-label={isConfirming ? 'Click again to confirm' : 'Delete thread'}
                      title={isConfirming ? 'Click again to confirm' : 'Delete thread'}
                    >
                      {isConfirming ? (
                        <span className="text-[10px] font-medium">Confirm?</span>
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                  {isActive && loadingHistory && (
                    <div className="absolute inset-0 flex items-center justify-center bg-card/80 rounded-lg">
                      <Loader2 className="w-4 h-4 animate-spin text-primary" />
                    </div>
                  )}
                </div>
              );
            })}
            {hasMore && (
              <button
                onClick={onLoadMore}
                disabled={loadingMore}
                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 mt-2 rounded-lg hover:bg-muted text-muted-foreground text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
              >
                {loadingMore ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
                Load more
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
