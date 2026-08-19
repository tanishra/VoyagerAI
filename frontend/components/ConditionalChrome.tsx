'use client';

import { usePathname } from 'next/navigation';
import Navbar from './Navbar';
import Footer from './Footer';
import { SmoothScroll } from './providers/SmoothScroll';

interface ConditionalChromeProps {
  children: React.ReactNode;
  locale: string;
}

export default function ConditionalChrome({ children, locale }: ConditionalChromeProps) {
  const pathname = usePathname();
  const isChatOrPrefs = pathname.includes('/chat') || pathname.includes('/preferences');

  if (isChatOrPrefs) {
    return <>{children}</>;
  }

  return (
    <SmoothScroll>
      <Navbar />
      <div id="main-content" className="flex-1 flex flex-col">
        {children}
      </div>
      <Footer />
    </SmoothScroll>
  );
}
