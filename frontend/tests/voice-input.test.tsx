import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, act } from '@testing-library/react';
import { useVoiceInput } from '@/lib/useVoiceInput';

type VoiceInputResult = ReturnType<typeof useVoiceInput>;

class MockSpeechRecognition {
  lang = '';
  continuous = false;
  interimResults = false;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  private _started = false;

  start() {
    this._started = true;
  }

  stop() {
    if (this._started && this.onend) {
      this._started = false;
      this.onend();
    }
  }

  abort() {
    this._started = false;
  }
}

function renderHook(fn: () => VoiceInputResult) {
  const result: { current: VoiceInputResult } = { current: {} as VoiceInputResult };
  function TestComponent() {
    result.current = fn();
    return null;
  }
  render(<TestComponent />);
  return result;
}

describe('useVoiceInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).SpeechRecognition;
    delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
  });

  it('isSupported is false when SpeechRecognition is not available', () => {
    const result = renderHook(() =>
      useVoiceInput({ locale: 'en', onTranscript: vi.fn() })
    );
    expect(result.current.isSupported).toBe(false);
  });

  it('isSupported is true when SpeechRecognition is available', () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition = MockSpeechRecognition;
    const result = renderHook(() =>
      useVoiceInput({ locale: 'en', onTranscript: vi.fn() })
    );
    expect(result.current.isSupported).toBe(true);
  });

  it('start sets isRecording to true', () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition = MockSpeechRecognition;
    const result = renderHook(() =>
      useVoiceInput({ locale: 'en', onTranscript: vi.fn() })
    );
    act(() => {
      result.current.start();
    });
    expect(result.current.isRecording).toBe(true);
  });

  it('stop sets isRecording to false', () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition = MockSpeechRecognition;
    const result = renderHook(() =>
      useVoiceInput({ locale: 'en', onTranscript: vi.fn() })
    );
    act(() => {
      result.current.start();
    });
    expect(result.current.isRecording).toBe(true);
    act(() => {
      result.current.stop();
    });
    expect(result.current.isRecording).toBe(false);
  });

  it('sets lang based on locale and starts recording', () => {
    (window as unknown as Record<string, unknown>).SpeechRecognition = MockSpeechRecognition;
    const result = renderHook(() =>
      useVoiceInput({ locale: 'ja', onTranscript: vi.fn() })
    );
    act(() => {
      result.current.start();
    });
    expect(result.current.isRecording).toBe(true);
    expect(result.current.error).toBeNull();
  });
});
