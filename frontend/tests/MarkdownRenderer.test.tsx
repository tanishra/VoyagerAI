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
    const { container } = render(<MarkdownRenderer content={`\`\`\`
const x = 1;
\`\`\``} />);
    expect(container.textContent).toContain('const x = 1');
  });

  it('renders inline code', () => {
    render(<MarkdownRenderer content="Use `npm install` to install" />);
    expect(screen.getByText('npm install')).toBeInTheDocument();
  });

  it('renders blockquotes', () => {
    render(<MarkdownRenderer content="> This is a quote" />);
    expect(screen.getByText('This is a quote')).toBeInTheDocument();
  });

  it('streaming: renders incomplete code fence without crashing', () => {
    render(<MarkdownRenderer content="Here is code:\n```js\nconst x = 1" streaming={true} />);
    expect(screen.getByText(/const x = 1/)).toBeInTheDocument();
  });

  it('streaming: renders incomplete bold without showing raw **', () => {
    render(<MarkdownRenderer content="This is **bold" streaming={true} />);
    const strong = screen.getByText('bold');
    expect(strong.tagName).toBe('STRONG');
  });

  it('streaming: renders incomplete italic without showing raw *', () => {
    render(<MarkdownRenderer content="This is *italic" streaming={true} />);
    const em = screen.getByText('italic');
    expect(em.tagName).toBe('EM');
  });

  it('streaming: complete markdown matches non-streaming render', () => {
    const md = '## Heading\n\n**bold** and *italic*\n\n- Item 1\n- Item 2';
    const { container: streamingContainer } = render(<MarkdownRenderer content={md} streaming={true} />);
    const { container: nonStreamingContainer } = render(<MarkdownRenderer content={md} streaming={false} />);
    expect(streamingContainer.innerHTML).toBe(nonStreamingContainer.innerHTML);
  });

  it('renders code block with syntax highlighting structure', () => {
    const { container } = render(<MarkdownRenderer content="```js\nconst x = 1;\n```" />);
    const codeElements = container.querySelectorAll('code');
    expect(codeElements.length).toBeGreaterThan(0);
  });
});
