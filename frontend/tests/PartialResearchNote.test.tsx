import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { Info } from 'lucide-react';
import en from '../messages/en.json';
import de from '../messages/de.json';
import es from '../messages/es.json';
import fr from '../messages/fr.json';
import hi from '../messages/hi.json';
import ja from '../messages/ja.json';

describe('PartialResearchNote i18n keys', () => {
  it('English locale has partialResearchNote key', () => {
    expect(en.chat.partialResearchNote).toBeDefined();
    expect(en.chat.partialResearchNote).toContain('partial research');
  });

  it('German locale has partialResearchNote key', () => {
    expect(de.chat.partialResearchNote).toBeDefined();
    expect(de.chat.partialResearchNote.length).toBeGreaterThan(10);
  });

  it('Spanish locale has partialResearchNote key', () => {
    expect(es.chat.partialResearchNote).toBeDefined();
    expect(es.chat.partialResearchNote.length).toBeGreaterThan(10);
  });

  it('French locale has partialResearchNote key', () => {
    expect(fr.chat.partialResearchNote).toBeDefined();
    expect(fr.chat.partialResearchNote.length).toBeGreaterThan(10);
  });

  it('Hindi locale has partialResearchNote key', () => {
    expect(hi.chat.partialResearchNote).toBeDefined();
    expect(hi.chat.partialResearchNote.length).toBeGreaterThan(10);
  });

  it('Japanese locale has partialResearchNote key', () => {
    expect(ja.chat.partialResearchNote).toBeDefined();
    expect(ja.chat.partialResearchNote.length).toBeGreaterThan(10);
  });
});

describe('PartialResearchNote rendering', () => {
  it('renders the note text with Info icon', () => {
    render(
      <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 shrink-0" data-testid="info-icon" />
          <span>en.chat.partialResearchNote</span>
        </div>
      </NextIntlClientProvider>
    );
    expect(screen.getByText('en.chat.partialResearchNote')).toBeInTheDocument();
    expect(screen.getByTestId('info-icon')).toBeInTheDocument();
  });
});
