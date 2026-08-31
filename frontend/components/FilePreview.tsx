'use client';

import { X, FileText } from 'lucide-react';
import type { UploadedFile } from '@/lib/upload-api';

interface FilePreviewProps {
  file: UploadedFile;
  onRemove: () => void;
}

export default function FilePreview({ file, onRemove }: FilePreviewProps) {
  const isImage = file.content_type.startsWith('image/');

  return (
    <div className="relative group shrink-0">
      {isImage ? (
        <img
          src={file.data_url}
          alt={file.filename}
          className="w-16 h-16 rounded-lg object-cover border border-border"
        />
      ) : (
        <div className="w-16 h-16 rounded-lg bg-muted border border-border flex flex-col items-center justify-center gap-1 px-1">
          <FileText className="w-5 h-5 text-muted-foreground" />
          <span className="text-[9px] text-muted-foreground truncate max-w-full">
            {file.filename}
          </span>
        </div>
      )}
      <button
        onClick={onRemove}
        className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center hover:bg-destructive/90 transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
        aria-label="Remove attachment"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}
