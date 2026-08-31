import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import FilePreview from '@/components/FilePreview';
import type { UploadedFile } from '@/lib/upload-api';

const mockFile: UploadedFile = {
  file_id: 'test-1',
  data_url: 'data:image/png;base64,iVBORw0KGgo=',
  filename: 'test.png',
  content_type: 'image/png',
  size: 1024,
};

const mockPdf: UploadedFile = {
  file_id: 'test-2',
  data_url: 'data:application/pdf;base64,JVBERi0=',
  filename: 'doc.pdf',
  content_type: 'application/pdf',
  size: 2048,
};

describe('FilePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders image thumbnail for image files', () => {
    render(<FilePreview file={mockFile} onRemove={vi.fn()} />);
    const img = screen.getByAltText('test.png');
    expect(img).toBeDefined();
    expect(img.tagName).toBe('IMG');
  });

  it('renders file icon for PDF files', () => {
    render(<FilePreview file={mockPdf} onRemove={vi.fn()} />);
    expect(screen.getByText('doc.pdf')).toBeDefined();
  });

  it('calls onRemove when X button is clicked', () => {
    const onRemove = vi.fn();
    render(<FilePreview file={mockFile} onRemove={onRemove} />);
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);
    expect(onRemove).toHaveBeenCalledOnce();
  });
});

describe('uploadFile', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('sends FormData with file to /upload endpoint', async () => {
    const { uploadFile } = await import('@/lib/upload-api');
    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        file_id: 'abc',
        data_url: 'data:image/png;base64,xxx',
        filename: 'test.png',
        content_type: 'image/png',
        size: 100,
      }),
    });
    global.fetch = mockFetch as any;

    const file = new File(['hello'], 'test.png', { type: 'image/png' });
    const result = await uploadFile(file);

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain('/upload');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result.file_id).toBe('abc');
  });

  it('throws error on non-ok response', async () => {
    const { uploadFile } = await import('@/lib/upload-api');
    const mockFetch = vi.fn().mockResolvedValue({
      status: 413,
      ok: false,
      json: async () => ({ detail: 'File is too large (max 10MB).' }),
    });
    global.fetch = mockFetch as any;

    const file = new File(['hello'], 'big.png', { type: 'image/png' });
    await expect(uploadFile(file)).rejects.toThrow('File is too large');
  });

  it('throws error on 415 unsupported type', async () => {
    const { uploadFile } = await import('@/lib/upload-api');
    const mockFetch = vi.fn().mockResolvedValue({
      status: 415,
      ok: false,
      json: async () => ({ detail: 'Unsupported file type.' }),
    });
    global.fetch = mockFetch as any;

    const file = new File(['hello'], 'test.txt', { type: 'text/plain' });
    await expect(uploadFile(file)).rejects.toThrow('Unsupported file type');
  });
});
