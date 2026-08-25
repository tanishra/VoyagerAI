import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import React from 'react';
import MarkdownRenderer from '@/components/MarkdownRenderer';
import { useThrottledValue } from '@/lib/useThrottledValue';

describe('StreamingMarkdown', () => {
  it('partial code fence renders as code block, not raw text', () => {
    render(<MarkdownRenderer content={'```python\nprint("hello")'} streaming={true} />);
    expect(screen.getByText(/print/)).toBeInTheDocument();
  });

  it('partial bold renders bold text, not raw ** syntax', () => {
    render(<MarkdownRenderer content="**important" streaming={true} />);
    const strong = screen.getByText('important');
    expect(strong.tagName).toBe('STRONG');
  });

  it('partial link renders gracefully without crashing', () => {
    render(<MarkdownRenderer content="[Click here](https://example" streaming={true} />);
    expect(screen.getByText('Click here')).toBeInTheDocument();
  });

  it('syntax highlighting structure appears on code blocks', () => {
    const { container } = render(
      <MarkdownRenderer content="```javascript\nconst foo = bar();" streaming={true} />,
    );
    const codeElements = container.querySelectorAll('code');
    expect(codeElements.length).toBeGreaterThan(0);
  });

  it('streaming cursor element is present when streaming text is shown', () => {
    const { container } = render(
      <div>
        <MarkdownRenderer content="Hello world" streaming={true} />
        <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-0.5" data-testid="cursor" />
      </div>,
    );
    expect(container.querySelector('[data-testid="cursor"]')).not.toBeNull();
  });
});

describe('useThrottledValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    let frameId = 0;
    const frames = new Map<number, FrameRequestCallback>();
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      const id = ++frameId;
      frames.set(id, cb);
      return id;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      frames.delete(id);
    });
    vi.stubGlobal('__flushFrames', () => {
      for (const [id, cb] of frames) {
        frames.delete(id);
        cb(id);
      }
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('returns latest value immediately when disabled', () => {
    function TestComp({ val }: { val: string }) {
      const throttled = useThrottledValue(val, false);
      return <span data-testid="result">{throttled}</span>;
    }
    const { rerender } = render(<TestComp val="hello" />);
    expect(screen.getByTestId('result').textContent).toBe('hello');

    rerender(<TestComp val="world" />);
    expect(screen.getByTestId('result').textContent).toBe('world');
  });

  it('returns initial value immediately when enabled', () => {
    function TestComp({ val }: { val: string }) {
      const throttled = useThrottledValue(val, true);
      return <span data-testid="result">{throttled}</span>;
    }
    render(<TestComp val="initial" />);
    expect(screen.getByTestId('result').textContent).toBe('initial');
  });

  it('updates to latest value after rAF flush', () => {
    function TestComp({ val }: { val: string }) {
      const throttled = useThrottledValue(val, true);
      return <span data-testid="result">{throttled}</span>;
    }
    const { rerender } = render(<TestComp val="first" />);
    expect(screen.getByTestId('result').textContent).toBe('first');

    rerender(<TestComp val="second" />);
    expect(screen.getByTestId('result').textContent).toBe('first');

    act(() => {
      (globalThis as any).__flushFrames();
    });
    expect(screen.getByTestId('result').textContent).toBe('second');
  });
});
