'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Download, Eye, EyeOff } from 'lucide-react';
import type { GeneratedImage } from '@/lib/types';

interface GeneratedImageCardProps {
  image: GeneratedImage;
}

export default function GeneratedImageCard({ image }: GeneratedImageCardProps) {
  const [expanded, setExpanded] = useState(false);

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = image.data_url;
    link.download = `voyager-${image.alt.slice(0, 30).replace(/\s+/g, '-')}.png`;
    link.click();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="mt-3 overflow-hidden rounded-xl border border-border bg-card"
    >
      <div className="relative">
        <Image
          src={image.data_url}
          alt={image.alt}
          width={800}
          height={600}
          unoptimized
          className={`w-full object-cover transition-all duration-300 ${
            expanded ? 'max-h-[600px]' : 'max-h-[300px]'
          }`}
        />
        <div className="absolute top-2 right-2 flex gap-1.5">
          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg bg-background/80 backdrop-blur-sm p-2 text-foreground hover:bg-background transition-colors"
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
          <button
            onClick={handleDownload}
            className="rounded-lg bg-background/80 backdrop-blur-sm p-2 text-foreground hover:bg-background transition-colors"
            title="Download"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="px-4 py-2.5 border-t border-border">
        <p className="text-xs text-muted-foreground truncate">{image.alt}</p>
      </div>
    </motion.div>
  );
}
