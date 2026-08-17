import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { useTranslations } from 'next-intl';
import en from '../messages/en.json';
import es from '../messages/es.json';
import fr from '../messages/fr.json';

function TestComponent() {
  const t = useTranslations('chat');
  return <div data-testid="localized-text">{t('placeholder')}</div>;
}

describe('locale switch re-renders strings', () => {
  it('renders English text with en locale', () => {
    render(
      <NextIntlClientProvider key="en" locale="en" messages={en}>
        <TestComponent />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId('localized-text')).toHaveTextContent(en.chat.placeholder);
  });

  it('renders Spanish text with es locale', () => {
    render(
      <NextIntlClientProvider key="es" locale="es" messages={es}>
        <TestComponent />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId('localized-text')).toHaveTextContent(es.chat.placeholder);
    expect(screen.getByTestId('localized-text')).not.toHaveTextContent(en.chat.placeholder);
  });

  it('renders French text with fr locale', () => {
    render(
      <NextIntlClientProvider key="fr" locale="fr" messages={fr}>
        <TestComponent />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId('localized-text')).toHaveTextContent(fr.chat.placeholder);
    expect(screen.getByTestId('localized-text')).not.toHaveTextContent(en.chat.placeholder);
  });

  it('switching locale changes rendered text', () => {
    const { rerender } = render(
      <NextIntlClientProvider key="en" locale="en" messages={en}>
        <TestComponent />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId('localized-text')).toHaveTextContent(en.chat.placeholder);

    rerender(
      <NextIntlClientProvider key="es" locale="es" messages={es}>
        <TestComponent />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId('localized-text')).toHaveTextContent(es.chat.placeholder);
    expect(screen.getByTestId('localized-text')).not.toHaveTextContent(en.chat.placeholder);
  });
});
