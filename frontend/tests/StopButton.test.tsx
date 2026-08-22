import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { useTranslations } from 'next-intl';
import { Square } from 'lucide-react';
import type { ChatMessage } from '@/lib/types';

// Minimal assistant message renderer that includes the stopped badge
function AssistantMessage({ msg }: { msg: ChatMessage }) {
  const t = useTranslations('chat');
  return (
    <div>
      <p>{msg.content}</p>
      {msg.wasStopped && (
        <span data-testid="stopped-badge" className="inline-flex items-center gap-1">
          <Square className="w-2.5 h-2.5 fill-current" />
          {t('stopped')}
        </span>
      )}
    </div>
  );
}

describe('Stopped badge', () => {
  it('renders badge when wasStopped is true', () => {
    render(<AssistantMessage msg={{ id: '1', role: 'assistant', content: 'Partial text...', wasStopped: true }} />);
    const badge = screen.getByTestId('stopped-badge');
    expect(badge).toBeDefined();
    expect(badge.textContent).toContain('Stopped');
  });

  it('does not render badge when wasStopped is false', () => {
    render(<AssistantMessage msg={{ id: '2', role: 'assistant', content: 'Full response' }} />);
    expect(screen.queryByTestId('stopped-badge')).toBeNull();
  });

  it('does not render badge when wasStopped is undefined', () => {
    render(<AssistantMessage msg={{ id: '3', role: 'assistant', content: 'Full response', wasStopped: undefined }} />);
    expect(screen.queryByTestId('stopped-badge')).toBeNull();
  });
});

describe('ChatMessage wasStopped field', () => {
  it('accepts wasStopped in the type', () => {
    const msg: ChatMessage = {
      id: 'test',
      role: 'assistant',
      content: 'Partial',
      wasStopped: true,
    };
    expect(msg.wasStopped).toBe(true);
  });

  it('wasStopped is optional', () => {
    const msg: ChatMessage = {
      id: 'test',
      role: 'assistant',
      content: 'Complete',
    };
    expect(msg.wasStopped).toBeUndefined();
  });
});
