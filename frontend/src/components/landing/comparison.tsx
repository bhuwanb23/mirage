"use client";

const ROWS = [
  ["Approach", "Detects after", "Trains before"],
  ["Input types", "Text only", "Text, voice, image, live"],
  ["Output", "Verdict only", "Evidence + debrief"],
  ["Personalization", "Generic", "Your real details"],
  ["Family protect", "No", "Yes — alerts"],
  ["Voice clone test", "No", "Yes — Fire Drill"],
];

export function Comparison() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 md:py-20">
      <h2 className="text-2xl font-semibold md:text-3xl">Why Mirage is Different</h2>
      <div className="mt-8 overflow-x-auto rounded-xl border border-border/60">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="border-b border-border/60 bg-card/40">
            <tr>
              <th className="px-4 py-3 font-medium text-muted-foreground"> </th>
              <th className="px-4 py-3 font-medium text-muted-foreground">Typical Tool</th>
              <th className="px-4 py-3 font-medium text-emerald-400">Mirage</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([feature, typical, mirage]) => (
              <tr key={feature} className="border-b border-border/40 last:border-0">
                <td className="px-4 py-3 font-medium">{feature}</td>
                <td className="px-4 py-3 text-muted-foreground">{typical}</td>
                <td className="bg-emerald-500/5 px-4 py-3 text-foreground">{mirage}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
