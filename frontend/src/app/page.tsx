import Link from "next/link";
import {
  Siren,
  PhoneCall,
  Radar,
  Bot,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const LAYERS = [
  {
    icon: Siren,
    title: "Scam Fire Drills",
    phase: "Phase 3",
    body: "A personalized scam simulation — bank KYC, fake parcel, OTP, fake job — built for your exposure. Then a debrief and a Resilience Score.",
    href: "/drill",
  },
  {
    icon: PhoneCall,
    title: "Live Call Guardian",
    phase: "Phase 4",
    body: "Real-time 5-stage pipeline detection on live calls: Hook → Authority → Isolation → Urgency → Payment. Plus a Memory Handshake only your family can answer.",
    href: "/guardian",
  },
  {
    icon: Radar,
    title: "Scammer Hunter",
    phase: "Phase 5",
    body: "An AI honeypot eats scam bait, extracts IOCs, and lights up a Neo4j Scam Graph as a weather map of active fraud.",
    href: "/graph",
  },
  {
    icon: Bot,
    title: "Zero-install Bot",
    phase: "Phase 2",
    body: "Forward a text, a voice note, or a screenshot to Telegram. Get a verdict and red flags in seconds — no app to install.",
    href: "/dashboard",
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-14">
      <section className="max-w-3xl">
        <Badge className="mb-4 gap-1.5" variant="secondary">
          <CheckCircle2 className="h-3 w-3" aria-hidden />
          Phase 0 · foundation
        </Badge>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Don&apos;t detect scams.
          <br />
          <span className="text-emerald-400">Vaccinate people against them.</span>
        </h1>
        <p className="mt-4 max-w-2xl text-muted-foreground">
          Mirage simulates a personalized attack against you <em>before</em> a real
          scammer ever reaches you — then debriefs you, scores your resilience, and
          shields you live when a real one calls.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/drill">
              Start a fire drill <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/dashboard">Open dashboard</Link>
          </Button>
        </div>
      </section>

      <section className="mt-14 grid gap-4 sm:grid-cols-2">
        {LAYERS.map((layer) => (
          <Card key={layer.title} className="border-border/60">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <layer.icon className="h-5 w-5 text-emerald-400" aria-hidden />
                <Badge variant="outline" className="font-mono text-[10px]">
                  {layer.phase}
                </Badge>
              </div>
              <CardTitle className="text-lg">{layer.title}</CardTitle>
              <CardDescription>{layer.body}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link
                href={layer.href}
                className="text-sm text-emerald-400 hover:underline"
              >
                Open →
              </Link>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="mt-14 rounded-lg border border-border/60 bg-card p-6">
        <h2 className="text-lg font-semibold">How the vaccine works</h2>
        <ol className="mt-3 grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
          <li>
            <span className="font-medium text-foreground">1. Simulate —</span> we
            build an attack aimed at you.
          </li>
          <li>
            <span className="font-medium text-foreground">2. Debrief —</span> you
            see exactly which hooks you missed.
          </li>
          <li>
            <span className="font-medium text-foreground">3. Shield —</span> a
            resilience score and live guardian from then on.
          </li>
        </ol>
      </section>
    </div>
  );
}
