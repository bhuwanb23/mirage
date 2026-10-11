export function LandingFooter() {
  return (
    <footer className="border-t border-border/60 py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
        <p>Mirage AI · Built for Forgehacks</p>
        <p>
          Report scams:{" "}
          <a
            className="text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            href="tel:1930"
          >
            1930
          </a>{" "}
          ·{" "}
          <a
            className="text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            href="https://cybercrime.gov.in"
            target="_blank"
            rel="noopener noreferrer"
          >
            cybercrime.gov.in
          </a>
        </p>
      </div>
    </footer>
  );
}
