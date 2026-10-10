"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import "leaflet/dist/leaflet.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, MapCity, MapHeatmap } from "@/lib/api";

const MapContainer = dynamic(
  () => import("react-leaflet").then((m) => m.MapContainer),
  { ssr: false },
);
const TileLayer = dynamic(
  () => import("react-leaflet").then((m) => m.TileLayer),
  { ssr: false },
);
const CircleMarker = dynamic(
  () => import("react-leaflet").then((m) => m.CircleMarker),
  { ssr: false },
);
const Popup = dynamic(() => import("react-leaflet").then((m) => m.Popup), {
  ssr: false,
});

/** Top scam type → marker colour (plan §5.5 legend). */
export const TYPE_COLORS: Record<string, string> = {
  bank_kyc: "#ef4444",
  upi_reversal: "#f97316",
  job_offer: "#3b82f6",
  fedex: "#a855f7",
  lottery: "#22c55e",
  impersonation: "#eab308",
  investment: "#06b6d4",
  electricity: "#facc15",
  relative_distress: "#f472b6",
};

const TYPE_LABELS: Record<string, string> = {
  bank_kyc: "Bank KYC",
  upi_reversal: "UPI Reversal",
  job_offer: "Job Offer",
  fedex: "FedEx / Parcel",
  lottery: "Lottery",
  impersonation: "Impersonation",
  investment: "Investment",
  electricity: "Electricity",
  relative_distress: "Relative in Distress",
};

const TREND_ICON: Record<string, string> = {
  increasing: "📈",
  decreasing: "📉",
  stable: "➡️",
};

function CityMarkers({ cities }: { cities: MapCity[] }) {
  return (
    <>
      {cities.map((c) => (
        <CircleMarker
          key={c.city}
          center={[c.lat, c.lng]}
          radius={6 + c.intensity * 18}
          pathOptions={{
            color: TYPE_COLORS[c.top_type] ?? "#ef4444",
            fillColor: TYPE_COLORS[c.top_type] ?? "#ef4444",
            fillOpacity: 0.35 + c.intensity * 0.35,
            weight: 2,
          }}
        >
          <Popup>
            <div style={{ minWidth: 160, fontFamily: "ui-monospace, monospace" }}>
              <strong>🏙️ {c.city}</strong>
              <br />
              {c.scam_count} scams this week
              <br />
              Top type: {TYPE_LABELS[c.top_type] ?? c.top_type}
              <br />
              Trend: {TREND_ICON[c.trend] ?? "➡️"} {c.trend}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

export default function ScamWeatherMap() {
  const [data, setData] = useState<MapHeatmap | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .mapHeatmap()
      .then(setData)
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 p-4 text-sm text-destructive">
        Map unavailable: {error}
      </div>
    );
  }

  const national = data?.national_stats ?? {};

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">Scam weather map — India</CardTitle>
          <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
            {Object.entries(TYPE_LABELS)
              .slice(0, 6)
              .map(([type, label]) => (
                <span key={type} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: TYPE_COLORS[type] }}
                    aria-hidden
                  />
                  {label}
                </span>
              ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[420px] w-full overflow-hidden rounded-md border border-border/60">
          {data ? (
            <MapContainer
              center={[22, 78]}
              zoom={5}
              style={{ height: "100%", width: "100%", background: "#09090b" }}
              attributionControl={false}
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
              <CityMarkers cities={data.cities} />
            </MapContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Loading heat data…
            </div>
          )}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <div className="rounded-md border border-border/60 p-2">
            <div className="text-muted-foreground">Reports this week</div>
            <div className="font-mono text-lg">
              {String(national.total_reports_this_week ?? "—")}
            </div>
          </div>
          <div className="rounded-md border border-border/60 p-2">
            <div className="text-muted-foreground">Top scam type</div>
            <div className="font-mono text-lg">
              {TYPE_LABELS[String(national.top_scam_type ?? "")] ??
                String(national.top_scam_type ?? "—")}
            </div>
          </div>
          <div className="rounded-md border border-border/60 p-2">
            <div className="text-muted-foreground">Trend</div>
            <div className="font-mono text-lg">
              {TREND_ICON[String(national.trend ?? "")] ?? "➡️"}{" "}
              {String(national.trend ?? "—")}
            </div>
          </div>
          <div className="rounded-md border border-border/60 p-2">
            <div className="text-muted-foreground">Graph rings</div>
            <div className="font-mono text-lg">
              {String(national.graph_rings_detected ?? "—")}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
