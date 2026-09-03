import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// Mock next-intl
vi.mock('next-intl', () => ({
  useTranslations: (namespace: string) => (key: string) => `${namespace}.${key}`,
}));

// Mock feedback-api
const { mockSubmitFeedback } = vi.hoisted(() => ({
  mockSubmitFeedback: vi.fn(),
}));
vi.mock('@/lib/feedback-api', () => ({
  submitFeedback: mockSubmitFeedback,
}));

import FeedbackButtons from '@/components/FeedbackButtons';

describe('FeedbackButtons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders thumbs up and thumbs down buttons', () => {
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    expect(screen.getByLabelText('chat.feedbackUp')).toBeInTheDocument();
    expect(screen.getByLabelText('chat.feedbackDown')).toBeInTheDocument();
  });

  it('clicking thumbs up calls submitFeedback with up rating', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'up' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    fireEvent.click(screen.getByLabelText('chat.feedbackUp'));
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        thread_id: 't1',
        message_id: 'm1',
        rating: 'up',
      });
    });
  });

  it('clicking thumbs down calls submitFeedback and shows comment textarea', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'down' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    fireEvent.click(screen.getByLabelText('chat.feedbackDown'));
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith({
        thread_id: 't1',
        message_id: 'm1',
        rating: 'down',
      });
    });
    await waitFor(() => {
      expect(screen.getByLabelText('chat.feedbackCommentPlaceholder')).toBeInTheDocument();
    });
  });

  it('clicking thumbs up highlights the up button', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'up' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    const upBtn = screen.getByLabelText('chat.feedbackUp');
    fireEvent.click(upBtn);
    await waitFor(() => {
      expect(upBtn.className).toContain('text-blue-500');
    });
  });

  it('clicking thumbs down highlights the down button', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'down' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    const downBtn = screen.getByLabelText('chat.feedbackDown');
    fireEvent.click(downBtn);
    await waitFor(() => {
      expect(downBtn.className).toContain('text-red-500');
    });
  });

  it('shows thanks message after successful submission', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'up' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    fireEvent.click(screen.getByLabelText('chat.feedbackUp'));
    await waitFor(() => {
      expect(screen.getByText('chat.feedbackThanks')).toBeInTheDocument();
    });
  });

  it('shows error message when submission fails', async () => {
    mockSubmitFeedback.mockRejectedValueOnce(new Error('Network error'));
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    fireEvent.click(screen.getByLabelText('chat.feedbackUp'));
    await waitFor(() => {
      expect(screen.getByText('chat.feedbackError')).toBeInTheDocument();
    });
  });

  it('submitting comment calls API with comment text', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'down' });
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'down' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);

    fireEvent.click(screen.getByLabelText('chat.feedbackDown'));
    await waitFor(() => {
      expect(screen.getByLabelText('chat.feedbackCommentPlaceholder')).toBeInTheDocument();
    });

    const textarea = screen.getByLabelText('chat.feedbackCommentPlaceholder') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Wrong prices' } });

    const submitBtn = screen.getByLabelText('chat.feedbackSubmit');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenLastCalledWith({
        thread_id: 't1',
        message_id: 'm1',
        rating: 'down',
        comment: 'Wrong prices',
      });
    });
  });

  it('clicking opposite thumb changes rating', async () => {
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'up' });
    mockSubmitFeedback.mockResolvedValueOnce({ status: 'ok', rating: 'down' });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);

    fireEvent.click(screen.getByLabelText('chat.feedbackUp'));
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByLabelText('chat.feedbackDown'));
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledTimes(2);
      expect(mockSubmitFeedback).toHaveBeenLastCalledWith({
        thread_id: 't1',
        message_id: 'm1',
        rating: 'down',
      });
    });
  });
});
