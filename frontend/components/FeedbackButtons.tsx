'use client';

import { useState, useCallback } from 'react';
import { ThumbsUp, ThumbsDown, Loader2, Send } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { submitFeedback } from '@/lib/feedback-api';

interface FeedbackButtonsProps {
  threadId: string;
  messageId: string;
}

export default function FeedbackButtons({ threadId, messageId }: FeedbackButtonsProps) {
  const t = useTranslations('chat');
  const [selected, setSelected] = useState<'up' | 'down' | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showThanks, setShowThanks] = useState(false);
  const [error, setError] = useState(false);

  const handleRate = useCallback(
    async (rating: 'up' | 'down') => {
      if (submitting) return;
      setSubmitting(true);
      setError(false);
      try {
        await submitFeedback({ thread_id: threadId, message_id: messageId, rating });
        setSelected(rating);
        if (rating === 'down') {
          setShowComment(true);
        } else {
          setShowComment(false);
          setComment('');
        }
        setShowThanks(true);
        setTimeout(() => setShowThanks(false), 3000);
      } catch {
        setError(true);
        setTimeout(() => setError(false), 3000);
      } finally {
        setSubmitting(false);
      }
    },
    [threadId, messageId, submitting],
  );

  const handleSubmitComment = useCallback(async () => {
    if (!comment.trim() || submitting) return;
    setSubmitting(true);
    setError(false);
    try {
      await submitFeedback({
        thread_id: threadId,
        message_id: messageId,
        rating: 'down',
        comment: comment.trim(),
      });
      setShowComment(false);
      setShowThanks(true);
      setTimeout(() => setShowThanks(false), 3000);
    } catch {
      setError(true);
      setTimeout(() => setError(false), 3000);
    } finally {
      setSubmitting(false);
    }
  }, [threadId, messageId, comment, submitting]);

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleRate('up')}
        disabled={submitting}
        className={`p-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
          selected === 'up'
            ? 'text-blue-500'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        }`}
        aria-label={t('feedbackUp')}
        title={t('feedbackUp')}
      >
        {submitting && selected === null ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <ThumbsUp className="w-3.5 h-3.5" />
        )}
      </button>
      <button
        onClick={() => handleRate('down')}
        disabled={submitting}
        className={`p-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
          selected === 'down'
            ? 'text-red-500'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        }`}
        aria-label={t('feedbackDown')}
        title={t('feedbackDown')}
      >
        {submitting && selected === null ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <ThumbsDown className="w-3.5 h-3.5" />
        )}
      </button>

      {showComment && (
        <div className="flex items-center gap-1 ml-1">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 1000))}
            placeholder={t('feedbackCommentPlaceholder')}
            className="text-xs bg-muted/50 border border-border rounded-lg px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 w-48 h-8"
            rows={1}
            aria-label={t('feedbackCommentPlaceholder')}
          />
          <button
            onClick={handleSubmitComment}
            disabled={submitting || !comment.trim()}
            className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t('feedbackSubmit')}
            title={t('feedbackSubmit')}
          >
            {submitting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      )}

      {showThanks && (
        <span className="text-[10px] text-green-500 ml-1">{t('feedbackThanks')}</span>
      )}

      {error && (
        <span className="text-[10px] text-red-500 ml-1">{t('feedbackError')}</span>
      )}
    </div>
  );
}
