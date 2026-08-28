"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  UserCheck, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  Send, 
  CreditCard, 
  RefreshCw, 
  Search,
  ShieldAlert,
  ArrowRight
} from "lucide-react";

interface StudentRecord {
  prospect_id: string;
  student_name: string;
  program: string;
  alternative_program?: string | null;
  status: string;
  is_qualified: boolean | null;
  student_id: string | null;
  sis_synced: boolean;
  history_logs: string[];
}

export default function AdminDashboard() {
  const [prospectId, setProspectId] = useState("");
  const [record, setRecord] = useState<StudentRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("Jordan Vance");
  const [email, setEmail] = useState("jordan@example.com");
  const [program, setProgram] = useState("BSc in Computer Science");
  const [transcript, setTranscript] = useState("High School GPA: 2.4. Mathematics: C, Physics: D, English: B.");

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const fetchStatus = async (id: string) => {
    if (!id) return;
    try {
      const res = await fetch(`${API_BASE}/students/${id}/status`);
      if (!res.ok) throw new Error("Prospect not found");
      const data = await res.json();
      setRecord(data);
      return data;
    } catch (err: any) {
      setError(err.message || "Failed to fetch status");
    }
  };

  const startPolling = (id: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    let attempts = 0;
    pollingRef.current = setInterval(async () => {
      attempts++;
      const updated = await fetchStatus(id);
      if (
        updated?.status === "OFFER_SENT" || 
        updated?.status === "AWAITING_REGISTRY_REVIEW" || 
        updated?.status === "FULLY_REGISTERED" || 
        updated?.status === "CLOSED" || 
        attempts > 15
      ) {
        if (pollingRef.current) clearInterval(pollingRef.current);
      }
    }, 1200);
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/prospects/inbound`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_name: name,
          student_email: email,
          target_program: program,
          transcript_text: transcript,
        }),
      });
      const data = await res.json();
      setProspectId(data.prospect_id);
      await fetchStatus(data.prospect_id);
      startPolling(data.prospect_id);
    } catch (err: any) {
      setError(err.message || "Ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRegistryDecision = async (decision: "APPROVE_DIRECT" | "APPROVE_ALTERNATIVE" | "REJECT") => {
    if (!record) return;
    setLoading(true);
    try {
      await fetch(`${API_BASE}/admissions/${record.prospect_id}/registry-override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          officer_notes: `Registry Officer authorized ${decision}`
        }),
      });
      await fetchStatus(record.prospect_id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptOffer = async () => {
    if (!record) return;
    setLoading(true);
    try {
      await fetch(`${API_BASE}/admissions/${record.prospect_id}/offer-response`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accepted: true }),
      });
      await fetchStatus(record.prospect_id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulatePayment = async () => {
    if (!record) return;
    setLoading(true);
    try {
      await fetch(`${API_BASE}/finance/webhooks/payment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prospect_id: record.prospect_id,
          amount_paid: 500.0,
          currency: "USD",
          payment_status: "COMPLETED",
          transaction_reference: `TXN-${Math.floor(100000 + Math.random() * 900000)}`,
        }),
      });
      startPolling(record.prospect_id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
      <div className="max-w-7xl mx-auto flex items-center justify-between pb-8 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <UserCheck className="w-7 h-7 text-indigo-400" />
            Campus Admissions &amp; Registry Sidecar
          </h1>
          <p className="text-sm text-slate-400 mt-1">Autonomous 5-Stage Orchestration Engine with HITL Registry Controls</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold rounded-full flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Agent &amp; HITL Gate Active
          </span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
        {/* Left Column */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-white mb-4">Ingest Inbound Prospect</h2>
            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Student Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Student Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Target Program</label>
                <input
                  type="text"
                  value={program}
                  onChange={(e) => setProgram(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Academic Transcript / GPA</label>
                <textarea
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2 rounded-lg text-sm transition flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" /> Trigger Ingestion &amp; Evaluation
              </button>
            </form>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Lookup Prospect State</h2>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. LEAD-ABC123"
                value={prospectId}
                onChange={(e) => setProspectId(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={() => fetchStatus(prospectId)}
                className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-1.5 border border-slate-700"
              >
                <Search className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-2 space-y-6">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl flex items-center gap-3 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {record ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <span className="text-xs text-slate-400 font-medium">Status</span>
                  <div className="text-base font-bold text-white mt-1 flex items-center gap-2 truncate">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 flex-shrink-0"></span>
                    {record.status}
                  </div>
                  <span className="text-xs text-slate-500 mt-1 block">ID: {record.prospect_id}</span>
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <span className="text-xs text-slate-400 font-medium">Student ID</span>
                  <div className="text-base font-bold text-emerald-400 mt-1 truncate">
                    {record.student_id || "Awaiting Payment"}
                  </div>
                  <span className="text-xs text-slate-500 mt-1 block">
                    {record.sis_synced ? "Synced to Core SIS" : "Pending SIS Sync"}
                  </span>
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <span className="text-xs text-slate-400 font-medium">Program Assignment</span>
                  <div className="text-sm font-semibold text-slate-200 mt-1 truncate">
                    {record.program}
                  </div>
                  <span className="text-xs text-indigo-400 mt-1 block truncate">
                    {record.is_qualified ? "Direct Entry" : "Review/Alternative Track"}
                  </span>
                </div>
              </div>

              {/* Stage 2 HITL Review Panel */}
              {record.status === "AWAITING_REGISTRY_REVIEW" && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold mb-2">
                    <ShieldAlert className="w-5 h-5" />
                    Stage 2 HITL Gate: Manual Admissions Officer Action Required
                  </div>
                  <p className="text-xs text-amber-200/80 mb-4">
                    The student did not meet standard GPA/prerequisite benchmarks for <strong>{record.program}</strong>.
                    Proposed alternative: <strong>{record.alternative_program || "General Foundation"}</strong>.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => handleRegistryDecision("APPROVE_DIRECT")}
                      disabled={loading}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-4 h-4" /> Approve Direct Entry Exception
                    </button>
                    <button
                      onClick={() => handleRegistryDecision("APPROVE_ALTERNATIVE")}
                      disabled={loading}
                      className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold px-4 py-2 rounded-lg transition flex items-center gap-1.5"
                    >
                      <ArrowRight className="w-4 h-4" /> Issue Alternative Offer
                    </button>
                    <button
                      onClick={() => handleRegistryDecision("REJECT")}
                      disabled={loading}
                      className="bg-red-600/80 hover:bg-red-600 text-white text-xs font-semibold px-4 py-2 rounded-lg transition"
                    >
                      Reject Application
                    </button>
                  </div>
                </div>
              )}

              {/* Stage 3 & 4 Progression Controls */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white">Stage Progression Controls</h3>
                  <button
                    onClick={() => fetchStatus(record.prospect_id)}
                    className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Refresh
                  </button>
                </div>

                <div className="flex flex-wrap gap-4">
                  <button
                    onClick={handleAcceptOffer}
                    disabled={loading || record.status !== "OFFER_SENT"}
                    className="bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 border border-slate-700 px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition"
                  >
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Accept Offer (Stage 3)
                  </button>

                  <button
                    onClick={handleSimulatePayment}
                    disabled={loading || record.status !== "OFFER_ACCEPTED"}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition"
                  >
                    <CreditCard className="w-4 h-4" />
                    Pay Fee &amp; Mint ID (Stages 4 &amp; 5)
                  </button>
                </div>
              </div>

              {/* Execution Audit Trail */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-sm font-semibold text-white mb-3">Live Execution Audit Trail</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-2 font-mono text-xs">
                  {record.history_logs?.map((log, idx) => (
                    <div key={idx} className="bg-slate-950 p-2.5 rounded border border-slate-800/80 text-slate-300">
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center text-slate-500">
              <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">Submit an inbound prospect or search by ID to inspect execution state.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}