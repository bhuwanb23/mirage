import { Comparison } from "@/components/landing/comparison";
import { FinalCta } from "@/components/landing/final-cta";
import { LandingFooter } from "@/components/landing/footer";
import { LandingHero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { ProblemStats } from "@/components/landing/problem-stats";

export default function Home() {
  return (
    <div className="flex flex-col">
      <LandingHero />
      <ProblemStats />
      <HowItWorks />
      <Comparison />
      <FinalCta />
      <LandingFooter />
    </div>
  );
}
