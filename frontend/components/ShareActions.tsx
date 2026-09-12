'use client';

import { useState, type RefObject } from 'react';
import { useTranslations } from 'next-intl';
import { Share2, MessageCircle, Mail, Link2, Download, Check } from 'lucide-react';
import { toPng } from 'html-to-image';

interface ShareActionsProps {
  shareUrl: string;
  destination: string;
  days: number;
  cost: string;
  cardRef: RefObject<HTMLDivElement | null>;
}

export default function ShareActions({ shareUrl, destination, days, cost, cardRef }: ShareActionsProps) {
  const t = useTranslations('share');
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const shareText = t('cardShareText', { destination, days, cost });

  async function handleWebShare() {
    if (navigator.share) {
      try {
        await navigator.share({
          title: t('cardShareTitle', { destination }),
          text: shareText,
          url: shareUrl,
        });
      } catch {
        // user cancelled
      }
    }
  }

  function handleWhatsApp() {
    const message = encodeURIComponent(`${shareText}\n${shareUrl}`);
    window.open(`https://wa.me/?text=${message}`, '_blank');
  }

  function handleEmail() {
    const subject = encodeURIComponent(t('cardEmailSubject', { destination }));
    const body = encodeURIComponent(`${shareText}\n\n${shareUrl}`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard not available
    }
  }

  async function handleDownloadImage() {
    if (!cardRef.current) return;
    setDownloading(true);
    try {
      const dataUrl = await toPng(cardRef.current, {
        pixelRatio: 2,
        cacheBust: true,
      });
      const link = document.createElement('a');
      link.download = `${destination.replace(/[^a-zA-Z0-9]/g, '_')}_voyagerai.png`;
      link.href = dataUrl;
      link.click();
    } catch {
      // download failed
    } finally {
      setDownloading(false);
    }
  }

  const buttonClass = 'flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border text-sm text-foreground hover:bg-muted hover:border-primary/40 transition-colors cursor-pointer';

  return (
    <div className="flex flex-wrap items-center gap-2 mt-6">
      {typeof navigator !== 'undefined' && typeof navigator.share === 'function' && (
        <button onClick={handleWebShare} className={`${buttonClass} bg-primary text-primary-foreground border-primary hover:bg-primary/90`}>
          <Share2 className="w-4 h-4" />
          {t('cardShare')}
        </button>
      )}
      <button onClick={handleWhatsApp} className={buttonClass} aria-label={t('cardWhatsapp')}>
        <MessageCircle className="w-4 h-4" />
        <span className="hidden sm:inline">{t('cardWhatsapp')}</span>
      </button>
      <button onClick={handleEmail} className={buttonClass} aria-label={t('cardEmail')}>
        <Mail className="w-4 h-4" />
        <span className="hidden sm:inline">{t('cardEmail')}</span>
      </button>
      <button onClick={handleCopyLink} className={buttonClass} aria-label={t('cardCopyLink')}>
        {copied ? <Check className="w-4 h-4 text-primary" /> : <Link2 className="w-4 h-4" />}
        <span className="hidden sm:inline">{copied ? t('cardCopied') : t('cardCopyLink')}</span>
      </button>
      <button onClick={handleDownloadImage} disabled={downloading} className={buttonClass} aria-label={t('cardDownloadImage')}>
        <Download className="w-4 h-4" />
        <span className="hidden sm:inline">{downloading ? t('cardDownloading') : t('cardDownloadImage')}</span>
      </button>
    </div>
  );
}
