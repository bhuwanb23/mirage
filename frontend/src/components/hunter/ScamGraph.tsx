"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { ForceGraphMethods } from "react-force-graph-2d";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, GraphData, GraphNode, GraphRings } from "@/lib/api";

// react-force-graph touches `window` — client-only.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center text-sm text-muted-foreground">
      Loading graph…
    </div>
  ),
});

export const NODE_COLORS: Record<string, string> = {
  PhoneNumber: "#ef4444",
  UPI_ID: "#f97316",
  Domain: "#a855f7",
  BankAccount: "#3b82f6",
  ScammerName: "#eab308",
};

const TYPE_LABELS: Record<string, string> = {
  PhoneNumber: "Phone",
  UPI_ID: "UPI ID",
  Domain: "Domain",
  BankAccount: "Bank A/c",
  ScammerName: "Name",
};

/**
 * react-force-graph's generics are loose (`{ [others: string]: any }`).
 * We accept its node/link shapes at the component boundary and narrow to
 * GraphNode inside the paint/click handlers.
 */
type ForceNode = {
  id?: string | number;
  x?: number;
  y?: number;
  [others: string]: unknown;
};

type ForceLink = { type?: string; [others: string]: unknown };

function nodeRadius(n: GraphNode): number {
  return 5 + Math.min(7, Math.log2(n.report_count + 1) * 2.5);
}

/** Paint nodes as colored shapes (circle/diamond/square/triangle/star). */
function paintNode(
  node: ForceNode,
  ctx: CanvasRenderingContext2D,
  globalScale: number,
) {
  const n = node as unknown as GraphNode & {
    x: number;
    y: number;
    __color?: string;
  };
  const color = NODE_COLORS[n.type] ?? "#a1a1aa";
  const r = nodeRadius(n);
  ctx.beginPath();
  if (n.type === "UPI_ID") {
    // diamond
    ctx.moveTo(n.x, n.y - r);
    ctx.lineTo(n.x + r, n.y);
    ctx.lineTo(n.x, n.y + r);
    ctx.lineTo(n.x - r, n.y);
    ctx.closePath();
  } else if (n.type === "Domain") {
    ctx.rect(n.x - r * 0.85, n.y - r * 0.85, r * 1.7, r * 1.7);
  } else if (n.type === "BankAccount") {
    ctx.moveTo(n.x, n.y - r);
    ctx.lineTo(n.x + r, n.y + r * 0.8);
    ctx.lineTo(n.x - r, n.y + r * 0.8);
    ctx.closePath();
  } else {
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI, false);
  }
  ctx.fillStyle = color;
  ctx.fill();

  if (n.in_ring) {
    // pulsing red ring border for confirmed scam-network members
    ctx.beginPath();
    ctx.arc(n.x, n.y, r + 3, 0, 2 * Math.PI, false);
    ctx.strokeStyle = "rgba(239,68,68,0.9)";
    ctx.lineWidth = 1.6 / globalScale + 1;
    ctx.stroke();
  }

  // label
  ctx.font = `${10 / globalScale}px ui-monospace, monospace`;
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(228,228,231,0.9)";
  ctx.fillText(n.label, n.x, n.y + r + 10 / globalScale);
}

export default function ScamGraph() {
  const [data, setData] = useState<GraphData | null>(null);
  const [rings, setRings] = useState<GraphRings | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.graphData(120), api.graphRings()])
      .then(([graph, ringData]) => {
        if (cancelled) return;
        setData(graph);
        setRings(ringData);
      })
      .catch((e) => !cancelled && setError(String(e.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, []);

  // FG mutates source/target into object refs — keep a lookup for the panel.
  const neighbors = useMemo(() => {
    const map = new Map<string, { node: GraphNode; rel: string }[]>();
    if (!data) return map;
    const byId = new Map(data.nodes.map((n) => [n.id, n]));
    for (const e of data.edges) {
      const a = byId.get(e.source);
      const b = byId.get(e.target);
      if (a && b) {
        map.set(e.source, [...(map.get(e.source) ?? []), { node: b, rel: e.type }]);
        map.set(e.target, [...(map.get(e.target) ?? []), { node: a, rel: e.type }]);
      }
    }
    return map;
  }, [data]);

  const selectById = useCallback(
    (id: string) => {
      if (!data) return;
      const node = data.nodes.find((n) => n.id === id);
      if (node) {
        setSelected(node);
        // force-graph assigns x/y at runtime (not in our GraphNode type).
        const pos = node as GraphNode & { x?: number; y?: number };
        fgRef.current?.centerAt(pos.x ?? 0, pos.y ?? 0, 600);
        fgRef.current?.zoom(3, 600);
      }
    },
    [data],
  );

  const handleNodeClick = useCallback((node: ForceNode) => {
    setSelected(node as unknown as GraphNode);
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
        Graph unavailable: {error}
      </div>
    );
  }

  const empty = data !== null && data.nodes.length === 0;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <Card className="border-border/60">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Live scam infrastructure</CardTitle>
        </CardHeader>
        <CardContent>
          {empty ? (
            <div className="flex h-[420px] flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
              <span className="text-2xl">🕸️</span>
              No scam data yet. Run the honeypot below or submit reports to
              populate the graph.
            </div>
          ) : (
            <div className="h-[420px] w-full overflow-hidden rounded-md bg-zinc-950/60">
              {data && (
                <ForceGraph2D
                  ref={fgRef}
                  graphData={{
                    nodes: data.nodes,
                    links: data.edges.map((e) => ({
                      source: e.source,
                      target: e.target,
                      type: e.type,
                    })),
                  }}
                  nodeId="id"
                  nodeCanvasObject={paintNode}
                  nodeCanvasObjectMode={() => "replace"}
                  backgroundColor="rgba(0,0,0,0)"
                  linkColor={(l: ForceLink) =>
                    l.type === "USES_UPI"
                      ? "#f97316"
                      : l.type === "LINKED_TO_DOMAIN"
                        ? "#a855f7"
                        : l.type === "DEPOSITS_TO"
                          ? "#3b82f6"
                          : "#52525b"
                  }
                  linkWidth={(l: ForceLink) => (l.type === "DEPOSITS_TO" ? 2.5 : 1.4)}
                  linkDirectionalParticles={1}
                  linkDirectionalParticleWidth={1.5}
                  onNodeClick={handleNodeClick}
                  cooldownTicks={120}
                  d3VelocityDecay={0.35}
                />
              )}
            </div>
          )}

          {/* legend */}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {Object.entries(TYPE_LABELS).map(([type, label]) => (
              <span key={type} className="flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: NODE_COLORS[type] }}
                  aria-hidden
                />
                {label}
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full border-2 border-red-500"
                aria-hidden
              />
              🔴 member of a detected scam ring
            </span>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {/* Node detail panel */}
        <Card className="border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Node details</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {selected ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 rounded-full"
                    style={{ backgroundColor: NODE_COLORS[selected.type] }}
                    aria-hidden
                  />
                  <span className="font-mono font-semibold">{selected.label}</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
                  <span>Type</span>
                  <span>{TYPE_LABELS[selected.type] ?? selected.type}</span>
                  <span>Reports</span>
                  <span className="font-mono">{selected.report_count}</span>
                  <span>First seen</span>
                  <span className="font-mono text-[11px]">
                    {String(selected.properties.first_seen ?? "—").slice(0, 10)}
                  </span>
                  <span>Last seen</span>
                  <span className="font-mono text-[11px]">
                    {String(selected.properties.last_seen ?? "—").slice(0, 10)}
                  </span>
                </div>
                {selected.properties.is_verified_scammer === true && (
                  <Badge className="bg-red-600/90 text-[10px]">
                    verified scammer (3+ reports)
                  </Badge>
                )}
                {selected.in_ring && (
                  <Badge variant="outline" className="border-red-500/60 text-[10px] text-red-400">
                    scam ring member
                  </Badge>
                )}
                <div className="pt-1 text-xs font-medium">Connected to</div>
                <ul className="space-y-1">
                  {(neighbors.get(selected.id) ?? []).map(({ node, rel }) => (
                    <li key={`${rel}-${node.id}`}>
                      <button
                        type="button"
                        onClick={() => selectById(node.id)}
                        className="text-left text-xs text-emerald-400 hover:underline"
                      >
                        {node.label}{" "}
                        <span className="text-muted-foreground">
                          ({TYPE_LABELS[node.type]}, {rel})
                        </span>
                      </button>
                    </li>
                  ))}
                  {(neighbors.get(selected.id) ?? []).length === 0 && (
                    <li className="text-xs text-muted-foreground">No edges in view.</li>
                  )}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Click a node in the graph — or a detected ring below — to inspect
                its reports, timestamps and connections.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Detected rings */}
        <Card className="border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Detected scam rings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(rings?.rings ?? []).length === 0 && (
              <p className="text-xs text-muted-foreground">
                No connected rings detected yet.
              </p>
            )}
            {(rings?.rings ?? []).map((ring) => (
              <button
                key={ring.ring_id}
                type="button"
                onClick={() => selectById(ring.node_ids[0])}
                className="w-full rounded-md border border-red-500/30 bg-red-500/5 p-2 text-left transition-colors hover:border-red-500/60"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-red-400">
                    🔴 Ring {ring.ring_id.replace("ring-", "")}
                  </span>
                  <span className="font-mono text-muted-foreground">
                    {ring.size} entities
                  </span>
                </div>
                <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                  {[...ring.phones, ...ring.upi_ids, ...ring.domains].slice(0, 4).join(" · ")}
                </div>
              </button>
            ))}
            {(rings?.shared.shared_upis.length ?? 0) > 0 && (
              <div className="pt-1 text-xs">
                <div className="font-medium">Shared UPI IDs</div>
                {rings!.shared.shared_upis.slice(0, 3).map((s) => (
                  <div key={s.upi_id} className="font-mono text-[11px] text-orange-400">
                    {s.upi_id} — {s.phone_count} phones
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
