import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MarkdownRenderer from '@/components/MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders plain text as a paragraph', () => {
    render(<MarkdownRenderer content="Hello world" />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('renders bold text', () => {
    render(<MarkdownRenderer content="This is **bold** text" />);
    const strong = screen.getByText('bold');
    expect(strong.tagName).toBe('STRONG');
  });

  it('renders italic text', () => {
    render(<MarkdownRenderer content="This is *italic* text" />);
    const em = screen.getByText('italic');
    expect(em.tagName).toBe('EM');
  });

  it('renders bullet lists', () => {
    render(<MarkdownRenderer content={`- Item 1
- Item 2
- Item 3`} />);
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Item 3')).toBeInTheDocument();
  });

  it('renders links with target=_blank and rel=noopener', () => {
    render(<MarkdownRenderer content="[Example](https://example.com)" />);
    const link = screen.getByText('Example');
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders GFM tables', () => {
    const tableMd = `| Col1 | Col2 |
|------|------|
| A    | B    |`;
    render(<MarkdownRenderer content={tableMd} />);
    expect(screen.getByText('Col1')).toBeInTheDocument();
    expect(screen.getByText('Col2')).toBeInTheDocument();
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders code blocks', () => {
    render(<MarkdownRenderer content={`\`\`\`
const x = 1;
\`\`\``} />);
    expect(screen.getByText('const x = 1;')).toBeInTheDocument();
  });

  it('renders inline code', () => {
    render(<MarkdownRenderer content="Use `npm install` to install" />);
    expect(screen.getByText('npm install')).toBeInTheDocument();
  });

  it('renders blockquotes', () => {
    render(<MarkdownRenderer content="> This is a quote" />);
    expect(screen.getByText('This is a quote')).toBeInTheDocument();
  });
});
