"use client";

export function AlertHistory({
  alerts,
}: {
  alerts: { summary: string; created_at: string }[];
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5">
      <h3 className="font-semibold">Alert history</h3>
      {alerts.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          No family alerts yet. When the bot or Guardian flags a high-risk scam, it
          shows up here.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {alerts.map((a, i) => (
            <li key={`${a.created_at}-${i}`} className="text-sm">
              <p className="font-medium">{a.summary}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(a.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
