"use client";

import { useState } from "react";
import { AlertTriangle, Copy, ExternalLink, Phone } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ReportResult } from "@/lib/api";

const SCAM_TYPE_OPTIONS = [
  { id: "bank_kyc", label: "Bank KYC Fraud" },
  { id: "upi_reversal", label: "UPI Reversal Scam" },
  { id: "fedex", label: "Fake Parcel / FedEx" },
  { id: "job_offer", label: "Fake Job Offer" },
  { id: "lottery", label: "Lottery / Prize" },
  { id: "relative_distress", label: "Relative in Distress" },
  { id: "otp_phishing", label: "OTP Phishing" },
  { id: "investment", label: "Investment Scam" },
  { id: "romance", label: "Romance Scam" },
  { id: "electricity", label: "Electricity Bill Scam" },
  { id: "impersonation", label: "Impersonation Scam" },
  { id: "unknown", label: "Other / Unknown" },
];

const CONTACT_OPTIONS = ["phone_call", "whatsapp", "sms", "email", "website"];

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="sm"
      variant="secondary"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1600);
        } catch {
          setCopied(false);
        }
      }}
    >
      <Copy className="mr-1 h-3.5 w-3.5" aria-hidden />
      {copied ? "Copied!" : label}
    </Button>
  );
}

export default function ReportGenerator({ honeypotSessionId }: { honeypotSessionId?: string }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [scamType, setScamType] = useState("bank_kyc");
  const [contact, setContact] = useState("phone_call");
  const [incidentDate, setIncidentDate] = useState("");
  const [incidentTime, setIncidentTime] = useState("");
  const [amountLost, setAmountLost] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.reportGenerate({
        user_name: name || null,
        user_phone: phone || null,
        user_city: city || null,
        scam_type: scamType,
        mode_of_contact: contact,
        incident_date: incidentDate || null,
        incident_time: incidentTime || null,
        amount_lost: Number(amountLost) || 0,
        anonymous,
        honeypot_session_id: honeypotSessionId || null,
      });
      setResult(res);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  const inputCls =
    "h-9 w-full rounded-md border border-border/60 bg-background px-3 text-sm outline-none focus:border-emerald-500/60";
  const labelCls = "text-xs text-muted-foreground";

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">Cybercrime report generator</CardTitle>
          {honeypotSessionId && (
            <Badge variant="outline" className="text-[10px] text-emerald-400">
              honeypot IOCs will be attached
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
          {/* Form */}
          <div className="space-y-2">
            <div>
              <label className={labelCls} htmlFor="rg-name">Your name</label>
              <input id="rg-name" className={inputCls} value={name}
                     onChange={(e) => setName(e.target.value)} placeholder="Priya Sharma" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls} htmlFor="rg-phone">Your phone</label>
                <input id="rg-phone" className={inputCls} value={phone}
                       onChange={(e) => setPhone(e.target.value)} placeholder="98111 22233" />
              </div>
              <div>
                <label className={labelCls} htmlFor="rg-city">City</label>
                <input id="rg-city" className={inputCls} value={city}
                       onChange={(e) => setCity(e.target.value)} placeholder="Mumbai" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls} htmlFor="rg-date">Incident date</label>
                <input id="rg-date" className={inputCls} value={incidentDate}
                       onChange={(e) => setIncidentDate(e.target.value)} placeholder="15 January 2025" />
              </div>
              <div>
                <label className={labelCls} htmlFor="rg-time">Time</label>
                <input id="rg-time" className={inputCls} value={incidentTime}
                       onChange={(e) => setIncidentTime(e.target.value)} placeholder="3:30 PM" />
              </div>
            </div>
            <div>
              <label className={labelCls} htmlFor="rg-type">Type of fraud</label>
              <select id="rg-type" className={inputCls} value={scamType}
                      onChange={(e) => setScamType(e.target.value)}>
                {SCAM_TYPE_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls} htmlFor="rg-contact">Mode of contact</label>
              <select id="rg-contact" className={inputCls} value={contact}
                      onChange={(e) => setContact(e.target.value)}>
                {CONTACT_OPTIONS.map((c) => (
                  <option key={c} value={c}>{c.replace("_", " ")}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls} htmlFor="rg-lost">Amount lost (₹)</label>
              <input id="rg-lost" className={inputCls} value={amountLost}
                     onChange={(e) => setAmountLost(e.target.value)} placeholder="0" inputMode="numeric" />
            </div>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" checked={anonymous}
                     onChange={(e) => setAnonymous(e.target.checked)} />
              Report anonymously
            </label>
            <Button className="w-full" onClick={() => void generate()} disabled={busy}>
              {busy ? "Generating…" : "Generate report"}
            </Button>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>

          {/* Output */}
          <div className="space-y-3">
            {result ? (
              <>
                {result.urgent && (
                  <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <span>
                      Money was lost — call <strong>1930</strong> IMMEDIATELY. The
                      faster you report, the higher the chance of recovery.
                    </span>
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {result.report_id}
                  </Badge>
                  <CopyButton text={result.report_text} label="Copy complaint" />
                  <CopyButton text={result.helpline_script} label="Copy 1930 script" />
                  <a href="tel:1930">
                    <Button size="sm" variant="outline">
                      <Phone className="mr-1 h-3.5 w-3.5" aria-hidden />
                      Call 1930
                    </Button>
                  </a>
                  <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
                    <Button size="sm" variant="outline">
                      <ExternalLink className="mr-1 h-3.5 w-3.5" aria-hidden />
                      Cyber Crime Portal
                    </Button>
                  </a>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs font-medium text-muted-foreground">
                      Complaint text (cybercrime.gov.in)
                    </div>
                    <pre className="h-[360px] overflow-auto whitespace-pre-wrap rounded-md border border-border/60 bg-zinc-950/60 p-3 font-mono text-[11px] leading-relaxed">
                      {result.report_text}
                    </pre>
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium text-muted-foreground">
                      1930 helpline script
                    </div>
                    <pre className="h-[360px] overflow-auto whitespace-pre-wrap rounded-md border border-border/60 bg-zinc-950/60 p-3 font-mono text-[11px] leading-relaxed">
                      {result.helpline_script}
                    </pre>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
                <span className="text-2xl">📄</span>
                <p>
                  Fill the form and generate a formatted complaint for
                  cybercrime.gov.in plus a read-aloud script for the 1930 helpline.
                  If a honeypot session is active, every extracted IOC is attached
                  automatically.
                </p>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
