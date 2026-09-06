import HeroSection from '@/components/HeroSection';
import HowItWorks from '@/components/HowItWorks';
import FeatureGrid from '@/components/FeatureGrid';
import CTASection from '@/components/CTASection';

export default function HomePage() {
  return (
    <main className="relative min-h-screen">
      <div className="relative z-10">
        <HeroSection />
        <HowItWorks />
        <FeatureGrid />
        <CTASection />
      </div>
    </main>
  );
}
