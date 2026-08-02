import HeroSection from '@/components/HeroSection';
import HowItWorks from '@/components/HowItWorks';
import FeatureGrid from '@/components/FeatureGrid';
import StatsSection from '@/components/StatsSection';
import CTASection from '@/components/CTASection';

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden pt-16">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-indigo-400/[0.08] rounded-full blur-[120px] animate-aurora" />
        <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-violet-400/[0.06] rounded-full blur-[100px] animate-float-slow" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-blue-300/[0.04] rounded-full blur-[140px]" />
      </div>

      <div
        className="pointer-events-none fixed inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative z-10">
        <HeroSection />
        <HowItWorks />
        <FeatureGrid />
        <StatsSection />
        <CTASection />
      </div>
    </main>
  );
}
