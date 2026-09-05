'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Plus, Trash2, MessageSquare, Loader2, ChevronDown, Link2, Copy as CopyIcon, Check, X, LogOut, Home, Settings, MoreHorizontal, Search, ArrowLeft, Bookmark, BookmarkCheck } from 'lucide-react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import type { ThreadMeta, SearchResult } from '@/lib/threads-api';
import { searchThreads } from '@/lib/threads-api';
import { listShares, revokeShare, type ShareLink } from '@/lib/share-api';
import { type SessionUser, logout } from '@/lib/auth';
import { useLocale } from '@/lib/useLocale';

function formatRelativeTime(timestamp: number): string {
  const now = Date.now() / 1000;
  const diff = now - timestamp;

  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(timestamp * 1000).toLocaleDateString();
}

function groupThreadsByDate(threads: ThreadMeta[]): { label: string; threads: ThreadMeta[] }[] {
  const now = Date.now() / 1000;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayStartTs = today.getTime() / 1000;
  const yesterdayStartTs = todayStartTs - 86400;
  const sevenDaysAgoTs = todayStartTs - 7 * 86400;

  const groups: { label: string; threads: ThreadMeta[] }[] = [
    { label: 'today', threads: [] },
    { label: 'yesterday', threads: [] },
    { label: 'previous7Days', threads: [] },
    { label: 'older', threads: [] },
  ];

  for (const thread of threads) {
    const ts = thread.updated_at || thread.created_at;
    if (ts >= todayStartTs) groups[0].threads.push(thread);
    else if (ts >= yesterdayStartTs) groups[1].threads.push(thread);
    else if (ts >= sevenDaysAgoTs) groups[2].threads.push(thread);
    else groups[3].threads.push(thread);
  }

  return groups.filter(g => g.threads.length > 0);
}

function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const idx = lowerText.indexOf(lowerQuery);
  if (idx === -1) return text;
  const before = text.slice(0, idx);
  const match = text.slice(idx, idx + query.length);
  const after = text.slice(idx + query.length);
  return (
    <>
      {before}
      <mark className="bg-primary/20 text-foreground rounded px-0.5">{match}</mark>
      {after}
    </>
  );
}

function Avatar({ user, size = 'sm' }: { user: SessionUser; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'w-8 h-8' : 'w-6 h-6';
  const text = size === 'md' ? 'text-xs' : 'text-[10px]';
  if (user.avatar_url) {
    return (
      <Image
        src={user.avatar_url}
        alt={user.display_name}
        width={size === 'md' ? 32 : 24}
        height={size === 'md' ? 32 : 24}
        className={`${dims} rounded-full object-cover border border-border`}
      />
    );
  }
  const initials = user.display_name
    .split(' ')
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  return (
    <div className={`${dims} rounded-full bg-primary/10 flex items-center justify-center ${text} font-semibold text-primary`}>
      {initials || '?'}
    </div>
  );
}

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
  onClose?: () => void;
  onTogglePin?: (threadId: string, pinned: boolean) => void;
  user: SessionUser | null;
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
  onClose,
  onTogglePin,
  user,
}: ThreadSidebarProps) {
  const t = useTranslations('threads');
  const tNav = useTranslations('nav');
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [deepSearchActive, setDeepSearchActive] = useState(false);
  const [deepSearchResults, setDeepSearchResults] = useState<SearchResult[]>([]);
  const [deepSearching, setDeepSearching] = useState(false);
  const [deepSearchTotal, setDeepSearchTotal] = useState(0);
  const [deepSearchHasMore, setDeepSearchHasMore] = useState(false);
  const [deepSearchOffset, setDeepSearchOffset] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [sharesExpanded, setSharesExpanded] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [revokingToken, setRevokingToken] = useState<string | null>(null);
  const [pinningId, setPinningId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listShares().then((result) => {
      if (!cancelled) setShares(result);
    });
    return () => { cancelled = true; };
  }, []);

  const handleCopy = async (e: React.MouseEvent, share: ShareLink) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(share.share_url);
      setCopiedToken(share.token);
      setTimeout(() => setCopiedToken(null), 2000);
    } catch {
      // clipboard not available
    }
  };

  const handleRevoke = async (e: React.MouseEvent, token: string) => {
    e.stopPropagation();
    setRevokingToken(token);
    const ok = await revokeShare(token);
    if (ok) {
      setShares((prev) => prev.filter((s) => s.token !== token));
    }
    setRevokingToken(null);
  };

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

  const handleTogglePin = async (e: React.MouseEvent, threadId: string, pinned: boolean) => {
    e.stopPropagation();
    if (!onTogglePin) return;
    setPinningId(threadId);
    setOpenMenu(null);
    onTogglePin(threadId, pinned);
    setPinningId(null);
  };

  const handleLogout = async () => {
    await logout();
    router.push(`/${locale}/login`);
  };

  const runDeepSearch = useCallback(async (query: string, offset: number = 0) => {
    if (!query.trim()) {
      setDeepSearchActive(false);
      setDeepSearchResults([]);
      setDeepSearchTotal(0);
      return;
    }
    setDeepSearching(true);
    try {
      const res = await searchThreads(query, offset);
      setDeepSearchResults(prev => offset === 0 ? res.results : [...prev, ...res.results]);
      setDeepSearchTotal(res.total);
      setDeepSearchHasMore(res.has_more);
      setDeepSearchOffset(offset);
    } catch {
      // network error — keep existing results
    } finally {
      setDeepSearching(false);
    }
  }, []);

  const handleDeepSearch = () => {
    if (!searchQuery.trim()) return;
    setDeepSearchActive(true);
    runDeepSearch(searchQuery, 0);
  };

  const handleClearDeepSearch = () => {
    setDeepSearchActive(false);
    setDeepSearchResults([]);
    setDeepSearchTotal(0);
    setDeepSearchHasMore(false);
  };

  const handleLoadMoreResults = () => {
    runDeepSearch(searchQuery, deepSearchOffset + 20);
  };

  const navLinks = [
    { href: `/${locale}`, icon: Home, key: 'home' },
    { href: `/${locale}/chat`, icon: MessageSquare, key: 'chat' },
    { href: `/${locale}/preferences`, icon: Settings, key: 'preferences' },
  ];

  const renderThreadItem = (thread: ThreadMeta) => {
    const isActive = thread.thread_id === activeThreadId;
    const isConfirming = confirmDelete === thread.thread_id;
    return (
      <div
        key={thread.thread_id}
        onClick={() => onSelect(thread.thread_id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect(thread.thread_id);
          }
        }}
        role="button"
        tabIndex={0}
        className={`group relative px-3 py-2 rounded-lg cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40 ${
          isActive ? 'bg-muted' : 'hover:bg-muted/50'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className={`text-sm truncate ${isActive ? 'text-foreground font-medium' : 'text-foreground/80'}`}>
              {thread.summary || t('untitled')}
            </p>
            <p className="text-[11px] text-muted-foreground/60 mt-0.5">
              {formatRelativeTime(thread.updated_at)}
            </p>
          </div>
          {/* Three-dot menu */}
          <div className="relative shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpenMenu(openMenu === thread.thread_id ? null : thread.thread_id);
                setConfirmDelete(null);
              }}
              className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
              aria-label={t('moreOptions')}
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
            {openMenu === thread.thread_id && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={(e) => { e.stopPropagation(); setOpenMenu(null); setConfirmDelete(null); }}
                />
                <div className="absolute right-0 top-7 z-50 min-w-[130px] rounded-lg border border-border bg-card shadow-lg py-1">
                  {isConfirming ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(e, thread.thread_id);
                        setOpenMenu(null);
                      }}
                      className="w-full px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 text-left cursor-pointer"
                    >
                      {t('confirmDeleteText')}
                    </button>
                  ) : (
                    <>
                      {onTogglePin && (
                        <button
                          onClick={(e) => handleTogglePin(e, thread.thread_id, !thread.pinned)}
                          disabled={pinningId === thread.thread_id}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-foreground hover:bg-muted text-left cursor-pointer disabled:opacity-50"
                        >
                          {thread.pinned ? (
                            <BookmarkCheck className="w-3 h-3" />
                          ) : (
                            <Bookmark className="w-3 h-3" />
                          )}
                          {thread.pinned ? t('unpin') : t('pin')}
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDelete(thread.thread_id);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 text-left cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                        {t('delete')}
                      </button>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
        {isActive && loadingHistory && (
          <div className="absolute inset-0 flex items-center justify-center bg-card/80 rounded-lg">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-[260px] shrink-0 bg-sidebar flex flex-col h-full border-r border-border/50">
      {/* Header — Logo + brand */}
      <div className="flex items-center justify-between px-3 h-14 border-b border-border/50 shrink-0">
        <Link
          href={`/${locale}`}
          className="flex items-center gap-2 font-bold text-sm text-foreground hover:text-primary transition-colors"
        >
          <span className="w-1 h-4 bg-primary rounded-full" />
          {tNav('brand')}
        </Link>
      </div>

      {/* New Chat button */}
      <div className="p-2.5 shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-muted text-sm font-medium text-foreground transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          {t('newChat')}
        </button>
      </div>

      {/* Search bar */}
      <div className="px-2.5 pb-2 shrink-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground/50" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (deepSearchActive) {
                if (debounceRef.current) clearTimeout(debounceRef.current);
                debounceRef.current = setTimeout(() => {
                  runDeepSearch(e.target.value, 0);
                }, 300);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleDeepSearch();
            }}
            placeholder={t('search')}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-muted/50 border-0 text-foreground placeholder:text-muted-foreground/50 outline-none focus:bg-muted focus:ring-2 focus:ring-primary/20 transition-all"
          />
        </div>
        {searchQuery.trim() && !deepSearchActive && (
          <button
            onClick={handleDeepSearch}
            className="mt-1.5 w-full flex items-center justify-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors cursor-pointer"
          >
            <Search className="w-3 h-3" />
            {t('searchAllMessages')}
          </button>
        )}
        {deepSearchActive && (
          <button
            onClick={handleClearDeepSearch}
            className="mt-1.5 w-full flex items-center justify-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-3 h-3" />
            {t('backToConversations')}
          </button>
        )}
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-2">
        {deepSearchActive ? (
          /* Deep search results */
          <div className="space-y-1">
            {deepSearching && deepSearchResults.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              </div>
            ) : deepSearchResults.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8 px-4">
                {t('noResults')}
              </p>
            ) : (
              <>
                <p className="text-[11px] text-muted-foreground/60 px-3 pt-2 pb-1">
                  {t('searchResults', { count: deepSearchTotal })}
                </p>
                {deepSearchResults.map((result) => (
                  <div
                    key={result.thread_id}
                    onClick={() => onSelect(result.thread_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelect(result.thread_id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    className={`group relative px-3 py-2 rounded-lg cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40 ${
                      result.thread_id === activeThreadId ? 'bg-muted' : 'hover:bg-muted/50'
                    }`}
                  >
                    <p className={`text-sm truncate ${result.thread_id === activeThreadId ? 'text-foreground font-medium' : 'text-foreground/80'}`}>
                      {result.summary || t('untitled')}
                    </p>
                    <p className="text-[11px] text-muted-foreground/70 mt-0.5 line-clamp-2">
                      {highlightMatch(result.snippet, searchQuery)}
                    </p>
                    <p className="text-[10px] text-muted-foreground/50 mt-0.5">
                      {formatRelativeTime(result.updated_at)}
                    </p>
                  </div>
                ))}
                {deepSearchHasMore && (
                  <button
                    onClick={handleLoadMoreResults}
                    disabled={deepSearching}
                    className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 mt-2 rounded-lg hover:bg-muted text-muted-foreground text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {deepSearching ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                    {t('loadMoreResults')}
                  </button>
                )}
              </>
            )}
          </div>
        ) : threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <MessageSquare className="w-7 h-7 text-muted-foreground/30 mb-2" />
            <p className="text-xs text-muted-foreground">
              {t('noConversations')}
            </p>
          </div>
        ) : searchQuery ? (
          /* Search results (flat list, no grouping) */
          (() => {
            const filtered = threads.filter(t =>
              (t.summary || '').toLowerCase().includes(searchQuery.toLowerCase())
            );
            if (filtered.length === 0) {
              return (
                <p className="text-xs text-muted-foreground text-center py-8 px-4">
                  {t('noResults')}
                </p>
              );
            }
            return (
              <div className="space-y-0.5">
                {filtered.map((thread) => renderThreadItem(thread))}
              </div>
            );
          })()
        ) : (
          /* Grouped thread list with pinned section */
          <>
            {(() => {
              const pinnedThreads = threads
                .filter(t => t.pinned)
                .sort((a, b) => (b.pinned_at || 0) - (a.pinned_at || 0));
              const unpinnedThreads = threads.filter(t => !t.pinned);

              return (
                <>
                  {pinnedThreads.length > 0 && (
                    <div>
                      <p className="text-[11px] font-medium text-muted-foreground/60 px-3 pt-3 pb-1">
                        {t('pinned')}
                      </p>
                      <div className="space-y-0.5">
                        {pinnedThreads.map((thread) => renderThreadItem(thread))}
                      </div>
                    </div>
                  )}
                  {groupThreadsByDate(unpinnedThreads).map((group) => (
                    <div key={group.label}>
                      <p className="text-[11px] font-medium text-muted-foreground/60 px-3 pt-3 pb-1">
                        {t(group.label)}
                      </p>
                      <div className="space-y-0.5">
                        {group.threads.map((thread) => renderThreadItem(thread))}
                      </div>
                    </div>
                  ))}
                </>
              );
            })()}
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
                {t('loadMore')}
              </button>
            )}
          </>
        )}
      </div>

      {/* Shared Links section */}
      <div className="border-t border-border/50 shrink-0">
        <button
          onClick={() => setSharesExpanded(!sharesExpanded)}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <Link2 className="w-3.5 h-3.5" />
            {t('sharedLinks')}
            {shares.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-medium">
                {shares.length}
              </span>
            )}
          </span>
          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${sharesExpanded ? 'rotate-180' : ''}`} />
        </button>
        {sharesExpanded && (
          <div className="px-2 pb-2 space-y-1 max-h-48 overflow-y-auto">
            {shares.length === 0 ? (
              <p className="text-[11px] text-muted-foreground px-3 py-2">
                {t('noSharedLinks')}
              </p>
            ) : (
              shares.map((share) => (
                <div
                  key={share.token}
                  className="group px-3 py-2 rounded-lg hover:bg-muted transition-colors"
                >
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs text-foreground truncate flex-1">
                      {share.destination}
                    </p>
                    <div className="flex items-center gap-0.5 shrink-0">
                      <button
                        onClick={(e) => handleCopy(e, share)}
                        className="p-1 rounded text-muted-foreground hover:text-foreground cursor-pointer"
                        aria-label={t('copyShareLink')}
                        title={t('copyLink')}
                      >
                        {copiedToken === share.token ? (
                          <Check className="w-3 h-3 text-chart-2" />
                        ) : (
                          <CopyIcon className="w-3 h-3" />
                        )}
                      </button>
                      <button
                        onClick={(e) => handleRevoke(e, share.token)}
                        disabled={revokingToken === share.token}
                        className="p-1 rounded text-muted-foreground hover:text-destructive cursor-pointer disabled:opacity-50"
                        aria-label={t('revokeShareLink')}
                        title={t('revoke')}
                      >
                        {revokingToken === share.token ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <X className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {t('expires', { time: formatRelativeTime(share.expires_at) })}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Footer — Nav links + user profile + logout */}
      <div className="border-t border-border/50 shrink-0 p-2.5 space-y-2">
        {/* Nav links */}
        <div className="flex items-center justify-around px-1">
          {navLinks.map((link) => {
            const active = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`p-2 rounded-lg transition-colors cursor-pointer ${
                  active
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
                aria-label={tNav(link.key)}
                title={tNav(link.key)}
              >
                <Icon className="w-4 h-4" />
              </Link>
            );
          })}
        </div>

        {/* User profile + logout */}
        {user && (
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted transition-colors">
            <Avatar user={user} size="md" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{user.display_name}</p>
              <p className="text-[10px] text-muted-foreground truncate">{user.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
              aria-label={tNav('signOut')}
              title={tNav('signOut')}
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
