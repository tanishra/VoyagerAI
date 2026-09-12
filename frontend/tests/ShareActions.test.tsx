import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import ShareActions from '@/components/ShareActions';
import en from '../messages/en.json';

vi.mock('html-to-image', () => ({
  toPng: vi.fn().mockResolvedValue('data:image/png;base64,mock'),
}));

const mockClipboard = vi.fn();
Object.defineProperty(navigator, 'clipboard', {
  value: { writeText: mockClipboard },
  configurable: true,
});

function renderWithProvider(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={en as Record<string, unknown>}>
      {ui}
    </NextIntlClientProvider>
  );
}

const defaultProps = {
  shareUrl: 'https://example.com/share/abc123',
  destination: 'Paris',
  days: 3,
  cost: '$1,200',
  cardRef: { current: document.createElement('div') },
};

describe('ShareActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders WhatsApp button', () => {
    renderWithProvider(<ShareActions {...defaultProps} />);
    expect(screen.getByLabelText('WhatsApp')).toBeInTheDocument();
  });

  it('renders Email button', () => {
    renderWithProvider(<ShareActions {...defaultProps} />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('renders Copy Link button', () => {
    renderWithProvider(<ShareActions {...defaultProps} />);
    expect(screen.getByLabelText('Copy Link')).toBeInTheDocument();
  });

  it('renders Download Image button', () => {
    renderWithProvider(<ShareActions {...defaultProps} />);
    expect(screen.getByLabelText('Download Image')).toBeInTheDocument();
  });

  it('opens WhatsApp link when clicked', () => {
    const spy = vi.spyOn(window, 'open').mockImplementation(() => null);
    renderWithProvider(<ShareActions {...defaultProps} />);
    fireEvent.click(screen.getByLabelText('WhatsApp'));
    expect(spy).toHaveBeenCalled();
    expect(spy.mock.calls[0][0]).toContain('wa.me');
    spy.mockRestore();
  });

  it('sets mailto href when email clicked', () => {
    const hrefSetter = vi.fn();
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        set href(v: string) { hrefSetter(v); },
      },
      configurable: true,
    });
    renderWithProvider(<ShareActions {...defaultProps} />);
    fireEvent.click(screen.getByLabelText('Email'));
    expect(hrefSetter).toHaveBeenCalledWith(expect.stringContaining('mailto:'));
  });

  it('copies link and shows confirmation', async () => {
    mockClipboard.mockResolvedValueOnce(undefined);
    renderWithProvider(<ShareActions {...defaultProps} />);
    fireEvent.click(screen.getByLabelText('Copy Link'));
    await waitFor(() => {
      expect(screen.getByLabelText('Copy Link')).toBeInTheDocument();
    });
  });

  it('downloads image when clicked', async () => {
    renderWithProvider(<ShareActions {...defaultProps} />);
    const btn = screen.getByLabelText('Download Image');
    fireEvent.click(btn);
    await waitFor(() => {
      expect(btn).toBeInTheDocument();
    });
  });
});
