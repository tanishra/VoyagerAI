'use client';

import { ThumbsUp, ThumbsDown, TrendingUp, MessageSquare } from 'lucide-react';
import { useTranslations } from 'next-intl';
import type { FeedbackAggregate } from '@/lib/feedback-api';

interface FeedbackSummaryProps {
  data: FeedbackAggregate | null;
}

export default function FeedbackSummary({ data }: FeedbackSummaryProps) {
  const t = useTranslations('admin');

  if (!data || data.total_ratings === 0) {
    return (
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">{t('feedbackTitle')}</h2>
        <p className="text-neutral-500 text-sm">{t('feedbackNoComments')}</p>
      </div>
    );
  }

  const ratioPercent = Math.round(data.satisfaction_ratio * 100);

  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">{t('feedbackTitle')}</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-neutral-800/50 border border-neutral-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-green-400 mb-2">
            <ThumbsUp className="w-4 h-4" />
            <span className="text-sm">{t('feedbackThumbsUp')}</span>
          </div>
          <p className="text-2xl font-bold">{data.total_up}</p>
        </div>

        <div className="bg-neutral-800/50 border border-neutral-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-red-400 mb-2">
            <ThumbsDown className="w-4 h-4" />
            <span className="text-sm">{t('feedbackThumbsDown')}</span>
          </div>
          <p className="text-2xl font-bold">{data.total_down}</p>
        </div>

        <div className="bg-neutral-800/50 border border-neutral-700 rounded-lg p-4">
          <div className="flex items-center gap-2 text-blue-400 mb-2">
            <TrendingUp className="w-4 h-4" />
            <span className="text-sm">{t('feedbackSatisfactionRatio')}</span>
          </div>
          <p className="text-2xl font-bold">{ratioPercent}%</p>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 text-neutral-400 mb-3">
          <MessageSquare className="w-4 h-4" />
          <span className="text-sm font-medium">{t('feedbackRecentComments')}</span>
        </div>
        {data.recent_comments.length === 0 ? (
          <p className="text-neutral-500 text-sm">{t('feedbackNoComments')}</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.recent_comments.map((c, i) => (
              <div
                key={i}
                className="bg-neutral-800/50 border border-neutral-700 rounded-lg p-3"
              >
                <p className="text-sm text-neutral-200">{c.comment}</p>
                <div className="flex items-center gap-2 mt-2 text-[10px] text-neutral-500">
                  <span>{t('threadId')}: {c.thread_id.slice(0, 12)}</span>
                  <span>·</span>
                  <span>{new Date(c.created_at * 1000).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
