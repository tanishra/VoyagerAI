'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

const LOCALE_MAP: Record<string, string> = {
  en: 'en-US',
  es: 'es-ES',
  fr: 'fr-FR',
  de: 'de-DE',
  hi: 'hi-IN',
  ja: 'ja-JP',
};

type SpeechRecognitionType = typeof window extends { SpeechRecognition: infer T }
  ? T
  : any;

function getSpeechRecognition(): SpeechRecognitionType | null {
  if (typeof window === 'undefined') return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

interface UseVoiceInputOptions {
  locale: string;
  onTranscript: (text: string) => void;
}

interface UseVoiceInputReturn {
  isSupported: boolean;
  isRecording: boolean;
  start: () => void;
  stop: () => void;
  error: string | null;
}

export function useVoiceInput({ locale, onTranscript }: UseVoiceInputOptions): UseVoiceInputReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<any>(null);
  const finalTranscriptRef = useRef<string>('');
  const onTranscriptRef = useRef(onTranscript);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const SpeechRecognition = getSpeechRecognition();
  const isSupported = SpeechRecognition !== null;

  const start = useCallback(() => {
    if (!SpeechRecognition) return;
    setError(null);
    finalTranscriptRef.current = '';

    const recognition = new SpeechRecognition();
    recognition.lang = LOCALE_MAP[locale] || 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: any) => {
      let finalText = '';
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalText += event.results[i][0].transcript;
        }
      }
      if (finalText) {
        finalTranscriptRef.current = finalText;
      }
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech') {
        setError('no-speech');
      } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setError('not-allowed');
      } else if (event.error === 'network') {
        setError('network');
      } else {
        setError(event.error || 'unknown');
      }
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
      if (finalTranscriptRef.current) {
        onTranscriptRef.current(finalTranscriptRef.current.trim());
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setIsRecording(true);
    } catch {
      setError('start-failed');
    }
  }, [SpeechRecognition, locale]);

  const stop = useCallback(() => {
    const recognition = recognitionRef.current;
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // already stopped
      }
    }
    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      const recognition = recognitionRef.current;
      if (recognition) {
        try {
          recognition.abort();
        } catch {
          // already stopped
        }
      }
    };
  }, []);

  return { isSupported, isRecording, start, stop, error };
}
