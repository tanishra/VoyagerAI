import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import GeneratedImageCard from '@/components/GeneratedImageCard';
import type { GeneratedImage } from '@/lib/types';

const mockImage: GeneratedImage = {
  data_url: 'data:image/png;base64,iVBORw0KGgo=',
  alt: 'Kyoto temple at sunset',
  prompt: 'Kyoto temple',
};

describe('GeneratedImageCard', () => {
  it('renders the image with correct src and alt', () => {
    render(<GeneratedImageCard image={mockImage} />);
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', mockImage.data_url);
    expect(img).toHaveAttribute('alt', mockImage.alt);
  });

  it('displays the alt text as caption', () => {
    render(<GeneratedImageCard image={mockImage} />);
    expect(screen.getByText(mockImage.alt)).toBeInTheDocument();
  });

  it('has expand and download buttons', () => {
    render(<GeneratedImageCard image={mockImage} />);
    expect(screen.getByTitle('Expand')).toBeInTheDocument();
    expect(screen.getByTitle('Download')).toBeInTheDocument();
  });

  it('toggles expanded state on expand button click', () => {
    render(<GeneratedImageCard image={mockImage} />);
    const expandBtn = screen.getByTitle('Expand');
    fireEvent.click(expandBtn);
    expect(screen.getByTitle('Collapse')).toBeInTheDocument();
  });

  it('triggers download on download button click', () => {
    const clickSpy = vi.fn();
    const linkEl = { href: '', download: '', click: clickSpy };
    const createElementSpy = vi.spyOn(document, 'createElement');

    render(<GeneratedImageCard image={mockImage} />);

    createElementSpy.mockReturnValue(linkEl as unknown as HTMLAnchorElement);
    fireEvent.click(screen.getByTitle('Download'));
    expect(clickSpy).toHaveBeenCalledOnce();
    expect(linkEl.href).toBe(mockImage.data_url);

    createElementSpy.mockRestore();
  });
});
