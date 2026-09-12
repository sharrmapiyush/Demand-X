import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

interface JobStats {
  total: number; with_district: number; without_district: number;
  by_district: Record<string, number>; by_source: Record<string, number>;
}
interface SkillDemandRow {
  skill_id: string; skill_name: string; distinct_job_count: number;
  mention_count: number; normalized_distinct_job_count: number;
  confidence: Record<string, number>; evidence_type_breakdown: Record<string, number>;
  verification_status: string;
}
interface SkillDemandResponse {
  rows: SkillDemandRow[]; total_jobs_evaluated: number;
  jobs_with_skill_evidence: number; skills_with_evidence: number;
  total_evidence_rows: number; source_id: string; observation_period: [string, string];
  rule_version: string;
  run_id: string;
  district: string | null; sector: string | null;
}
interface GapRow {
  skill_id: string; skill_name: string; gap_status: string;
  demand_distinct_job_count: number; demand_mention_count: number;
  demand_normalized_distinct_job_count: number;
  has_dvet_supply_evidence: boolean;
  dvet_supply_detail: any; demand_confidence: Record<string, number>;
  verification_status: string;
}
interface GapResponse {
  rows: GapRow[]; count: number; total_jobs_evaluated: number;
  gap_summary: Record<string, number>; gap_thresholds: any;
  dvet_institute_count: number; dvet_trades_total: number;
  dvet_extrapolation_note: string;
}
interface Recommendation {
  skill_id: string; skill_name: string; recommendation: string;
  reason: string; priority: string; confidence: string;
  evidence: string; next_action: string; data_quality: string;
}
interface RecommendationsResponse {
  recommendations: Recommendation[]; count: number;
  total_jobs_evaluated: number; rule_version: string; note: string;
}
interface DvetSupply {
  snapshot_source: string; institute_count: number; institute_name: string;
  total_trades: number; total_intake: number;
  skills_with_supply_evidence: Record<string, { trades: string[]; count: number }>;
  occupations_with_supply_evidence: Record<string, { trades: string[]; count: number }>;
  extrapolation_note: string;
}
interface SourceHealth {
  source_id: string; source_name: string; status: string;
  last_fetched_at: string | null; freshness_class: string; reliability_notes: string | null;
}
interface RAGResponse {
  answer: string; confidence: string; evidence_count: number;
  source_freshness: string; disclaimer: string;
  evidence: Array<{ type: string; id: string; title: string; snippet: string }>;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Design tokens
// ═══════════════════════════════════════════════════════════════════════════════

const C = {
  navy: '#0B3D66', navyDark: '#082A47', teal: '#0E7C7B', tealLight: '#E6F5F4',
  gold: '#C9960C', goldLight: '#FFF8E6', green: '#1E8E5A', greenLight: '#E6F7EF',
  red: '#C53030', redLight: '#FFF5F5', blue: '#3182CE', blueLight: '#EBF4FF',
  gray: '#5B6B79', grayLight: '#94A3B8', grayXLight: '#CBD5E1',
  lightBg: '#F0F4F8', border: '#DCE3E8', borderLight: '#E8EDF2',
  white: '#FFFFFF', dark: '#1A2733', darkSubtle: '#374151',
  bg: '#F7F9FC', sidebarW: 240,
}
const PIE = ['#0B3D66','#0E7C7B','#C9960C','#3182CE','#1E8E5A','#805AD5','#DD6B20','#E53E3E']

// ═══════════════════════════════════════════════════════════════════════════════
// Hooks & shared components
// ═══════════════════════════════════════════════════════════════════════════════

function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    setLoading(true); setError(null)
    fetch(url).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [url])
  return { data, loading, error }
}

function KPICard({ label, value, sub, color, icon }: {
  label: string; value: string | number; sub?: string; color?: string; icon?: string;
}) {
  return (
    <div style={{
      background: C.white, border: `1px solid ${C.border}`, borderRadius: 10,
      padding: '18px 20px', minWidth: 170, flex: '1 1 170px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ fontSize: 11, color: C.gray, textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 500 }}>
          {label}
        </div>
        {icon && <span style={{ fontSize: 16, opacity: 0.6 }}>{icon}</span>}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || C.dark, marginTop: 6, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: C.gray, marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function Badge({ status, size }: { status: string; size?: 'sm' | 'md' }) {
  const map: Record<string, [string, string]> = {
    ONLINE: [C.green, C.greenLight], DEGRADED: [C.gold, C.goldLight], OFFLINE: [C.red, C.redLight],
    HISTORICAL: [C.gray, C.lightBg], PERIODIC: [C.teal, C.tealLight], LIVE: [C.green, C.greenLight],
    STATIC: [C.gray, C.lightBg], NEEDS_REVIEW: [C.gold, C.goldLight], VERIFIED: [C.green, C.greenLight],
    HIGH_GAP: [C.red, C.redLight], MEDIUM_GAP: [C.gold, C.goldLight], LOW_GAP: [C.teal, C.tealLight],
    NO_DATA: [C.gray, C.lightBg], OBSERVED: [C.green, C.greenLight], ESTIMATED: [C.gold, C.goldLight],
    BLOCKED: [C.red, C.redLight], HIGH: [C.red, C.redLight], MEDIUM: [C.gold, C.goldLight],
    LOW: [C.gray, C.lightBg],
  }
  const [fg, bg] = map[status] || [C.gray, C.lightBg]
  const fs = size === 'sm' ? 10 : 11
  return (
    <span style={{
      display: 'inline-block', padding: size === 'sm' ? '1px 6px' : '2px 8px',
      borderRadius: 4, fontSize: fs, fontWeight: 600, color: fg, backgroundColor: bg,
      whiteSpace: 'nowrap',
    }}>{status}</span>
  )
}

function Card({ title, children, style, right }: {
  title?: string; children: React.ReactNode; style?: React.CSSProperties; right?: React.ReactNode;
}) {
  return (
    <div style={{
      background: C.white, borderRadius: 10, border: `1px solid ${C.border}`,
      padding: '20px 24px', marginBottom: 20,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)', ...style,
    }}>
      {title && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: C.dark }}>{title}</h3>
          {right}
        </div>
      )}
      {children}
    </div>
  )
}

function Provenance({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'inline-block', padding: '5px 12px', backgroundColor: C.lightBg,
      border: `1px solid ${C.borderLight}`, borderRadius: 4, fontSize: 11, color: C.gray,
      fontFamily: "'SF Mono', 'Consolas', monospace", marginTop: 10,
    }}>{children}</div>
  )
}

function Loading() {
  return <div style={{ padding: 20, color: C.gray, fontSize: 13 }}>Loading…</div>
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <div style={{ padding: 12, backgroundColor: C.redLight, border: `1px solid #FEB2B2`,
      borderRadius: 6, color: '#9B2C2C', fontSize: 13 }}>
      Error: {msg}
    </div>
  )
}

function Empty({ msg }: { msg: string }) {
  return <p style={{ color: C.gray, fontSize: 13, padding: 10 }}>{msg}</p>
}

function EvidenceDrawer({ open, onClose, children }: {
  open: boolean; onClose: () => void; children: React.ReactNode;
}) {
  if (!open) return null
  return (
    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 480, maxWidth: '100vw',
      background: C.white, boxShadow: '-4px 0 24px rgba(0,0,0,0.12)', zIndex: 1000,
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${C.border}`, display: 'flex',
        justifyContent: 'space-between', alignItems: 'center' }}>
        <strong style={{ fontSize: 15 }}>Evidence & Details</strong>
        <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20,
          cursor: 'pointer', color: C.gray }}>✕</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>{children}</div>
    </div>
  )
}

function FilterBar({ district, setDistrict, sector, setSector }: {
  district: string; setDistrict: (v: string) => void;
  sector: string; setSector: (v: string) => void;
}) {
  const districts = ['', 'Pune', 'Mumbai', 'Nashik', 'Nagpur', 'Thane', 'Aurangabad',
    'Kolhapur', 'Solapur', 'Satara', 'Ahmednagar', 'Jalgaon']
  const sectors = ['', 'IT-ITeS', 'Automotive/Manufacturing', 'Electronics', 'Personal Care']
  const selectStyle: React.CSSProperties = {
    padding: '7px 12px', border: `1px solid ${C.border}`, borderRadius: 6,
    fontSize: 13, backgroundColor: C.white, color: C.dark, cursor: 'pointer', minWidth: 160,
  }
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, color: C.gray, fontWeight: 500 }}>DISTRICT</span>
      <select value={district} onChange={e => setDistrict(e.target.value)} style={selectStyle}>
        <option value="">All Districts</option>
        {districts.filter(Boolean).map(d => <option key={d} value={d}>{d}</option>)}
      </select>
      <span style={{ fontSize: 12, color: C.gray, fontWeight: 500 }}>SECTOR</span>
      <select value={sector} onChange={e => setSector(e.target.value)} style={selectStyle}>
        <option value="">All Sectors</option>
        {sectors.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
      </select>
    </div>
  )
}

function DataTable({ columns, rows, onRowClick }: {
  columns: { key: string; label: string; align?: string; width?: number; render?: (v: any, row: any) => React.ReactNode }[];
  rows: any[]; onRowClick?: (row: any) => void;
}) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: `2px solid ${C.border}` }}>
            {columns.map(c => (
              <th key={c.key} style={{
                padding: '8px 10px', textAlign: (c.align as any) || 'left',
                fontSize: 11, color: C.gray, textTransform: 'uppercase', letterSpacing: 0.4,
                fontWeight: 600, width: c.width,
              }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{
              borderBottom: `1px solid ${C.borderLight}`, cursor: onRowClick ? 'pointer' : 'default',
              transition: 'background 0.1s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = C.lightBg }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent' }}
            onClick={() => onRowClick?.(row)}
            >
              {columns.map(c => (
                <td key={c.key} style={{
                  padding: '7px 10px', textAlign: (c.align as any) || 'left',
                }}>
                  {c.render ? c.render(row[c.key], row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <Empty msg="No data available for current filters." />}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Dashboard
// ═══════════════════════════════════════════════════════════════════════════════

function DashboardPage({ district, sector }: { district: string; sector: string }) {
  const q = `?source_id=naukri-historical-promptcloud${district ? `&district=${district}` : ''}${sector ? `&sector=${sector}` : ''}`
  const jobs = useFetch<JobStats>('/api/v1/jobs/stats')
  const skillDemand = useFetch<SkillDemandResponse>(`/api/v1/skills/demand${q}&limit=10`)
  const gaps = useFetch<GapResponse>(`/api/v1/skills/gaps${q}`)
  const supply = useFetch<{ dvet_supply_summary: DvetSupply }>('/api/v1/skills/supply')
  const sources = useFetch<{ sources: SourceHealth[] }>('/api/v1/governance/health')

  const topSkills = useMemo(() => {
    if (!skillDemand.data) return []
    return skillDemand.data.rows.slice(0, 8)
  }, [skillDemand.data])

  const highGaps = useMemo(() => {
    if (!gaps.data) return []
    return gaps.data.rows.filter(r => r.gap_status === 'HIGH_GAP')
  }, [gaps.data])

  const distChart = useMemo(() => {
    if (!jobs.data) return []
    return Object.entries(jobs.data.by_district)
      .sort((a, b) => b[1] - a[1]).slice(0, 10)
      .map(([d, c]) => ({ district: d.length > 12 ? d.slice(0, 10) + '…' : d, full: d, jobs: c }))
  }, [jobs.data])

  const occChart = useMemo(() => {
    if (!gaps.data) return []
    return [
      { name: 'HIGH_GAP', value: gaps.data.gap_summary.HIGH_GAP || 0 },
      { name: 'MEDIUM_GAP', value: gaps.data.gap_summary.MEDIUM_GAP || 0 },
      { name: 'LOW_GAP', value: gaps.data.gap_summary.LOW_GAP || 0 },
      { name: 'NEEDS_REVIEW', value: gaps.data.gap_summary.NEEDS_REVIEW || 0 },
      { name: 'NO_DATA', value: gaps.data.gap_summary.NO_DATA || 0 },
    ].filter(x => x.value > 0)
  }, [gaps.data])

  const location = district || 'All Districts'
  const secLabel = sector || 'All Sectors'

  return (
    <>
      {/* Demo insights */}
      <Card title="Key Findings" style={{ borderLeft: `4px solid ${C.teal}`, background: '#FAFCFD' }}>
        <div style={{ fontSize: 13, color: C.darkSubtle, lineHeight: 1.8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <strong>📍 Location:</strong> {location} · <strong>Sector:</strong> {secLabel}
            </div>
            <div>
              <strong>📊 Jobs analyzed:</strong> {jobs.data?.total?.toLocaleString() || '—'}
            </div>
            <div>
              <strong>🎯 Skills with evidence:</strong> {skillDemand.data?.skills_with_evidence || '—'} of 32 canonical
            </div>
            <div>
              <strong>⚠️ High gaps identified:</strong> {highGaps.length} skill{highGaps.length !== 1 ? 's' : ''}
            </div>
          </div>
          <Provenance>
            Evidence-grounded. No synthetic data. Rule: {skillDemand.data?.rule_version || 'mvp-v1'} ·
            Source: {skillDemand.data?.source_id || '—'}
          </Provenance>
        </div>
      </Card>

      {/* KPI cards */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 20 }}>
        <KPICard label="Total Jobs" value={jobs.data?.total?.toLocaleString() || '—'} icon="📋" color={C.navy}
          sub={`${jobs.data?.with_district?.toLocaleString() || 0} with district evidence`} />
        <KPICard label="Skills Tracked" value={skillDemand.data?.skills_with_evidence || 0} icon="🎯" color={C.teal}
          sub="of 32 canonical skills" />
        <KPICard label="Training Trades" value={supply.data?.dvet_supply_summary?.total_trades || 0} icon="🏫" color={C.gold}
          sub={`${supply.data?.dvet_supply_summary?.institute_count || 0} institute(s)`} />
        <KPICard label="High Skill Gaps" value={highGaps.length} icon="⚠️" color={highGaps.length > 0 ? C.red : C.green}
          sub="demand without supply evidence" />
        <KPICard label="Sources Online"
          value={`${(sources.data?.sources || []).filter(s => s.status === 'ONLINE').length}/${(sources.data?.sources || []).length || 0}`}
          icon="✅" color={C.green} sub="source health" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <Card title="Top Demanded Skills">
          {skillDemand.loading ? <Loading /> : topSkills.length === 0 ? <Empty msg="No skill demand data." /> : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topSkills.map(r => ({
                name: r.skill_name.length > 18 ? r.skill_name.slice(0, 16) + '…' : r.skill_name,
                full: r.skill_name, jobs: r.distinct_job_count,
              }))} margin={{ top: 5, right: 15, bottom: 30, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.borderLight} />
                <XAxis dataKey="name" angle={-30} textAnchor="end" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: any) => [v, 'Distinct Jobs']}
                  labelFormatter={l => l} />
                <Bar dataKey="jobs" fill={C.teal} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Skill Gap Distribution">
          {gaps.loading ? <Loading /> : occChart.length === 0 ? <Empty msg="No gap data." /> : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={occChart} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={100} innerRadius={40}
                  label={({ name, value }) => `${name}: ${value}`}>
                  {occChart.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
                </Pie>
                <Legend verticalAlign="bottom" height={36} />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Jobs by district */}
      {distChart.length > 0 && (
        <Card title="Jobs by District">
          <ResponsiveContainer width="100%" height={Math.max(240, distChart.length * 32)}>
            <BarChart data={distChart} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.borderLight} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="district" type="category" tick={{ fontSize: 11 }} width={95} />
              <Tooltip formatter={(v: any) => [String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ','), 'Jobs']} />
              <Bar dataKey="jobs" fill={C.navy} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <Provenance>District counts from persisted job_postings. {jobs.data?.without_district || 0} jobs lack district evidence.</Provenance>
        </Card>
      )}

      {/* Source freshness */}
      {sources.data && sources.data.sources.length > 0 && (
        <Card title="Data Sources & Freshness">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {sources.data.sources.map(s => (
              <div key={s.source_id} style={{
                padding: '10px 14px', border: `1px solid ${C.border}`, borderRadius: 8,
                flex: '1 1 260px', background: C.white,
              }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{s.source_name}</div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Badge status={s.status} /> <Badge status={s.freshness_class} size="sm" />
                </div>
                <div style={{ fontSize: 11, color: C.gray, marginTop: 4 }}>
                  {s.last_fetched_at ? `Last: ${new Date(s.last_fetched_at).toLocaleDateString()}` : 'Not yet fetched'}
                </div>
              </div>
            ))}
          </div>
          <Provenance>Health telemetry from persisted Source registry — not fabricated.</Provenance>
        </Card>
      )}
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Skill Intelligence
// ═══════════════════════════════════════════════════════════════════════════════

function SkillsPage({ district, sector }: { district: string; sector: string }) {
  const q = `?source_id=naukri-historical-promptcloud${district ? `&district=${district}` : ''}${sector ? `&sector=${sector}` : ''}`
  const skillDemand = useFetch<SkillDemandResponse>(`/api/v1/skills/demand${q}&limit=32`)
  const [search, setSearch] = useState('')
  const [selectedSkill, setSelectedSkill] = useState<SkillDemandRow | null>(null)

  const rows = useMemo(() => {
    if (!skillDemand.data) return []
    return skillDemand.data.rows.filter(r =>
      !search || r.skill_name.toLowerCase().includes(search.toLowerCase()) || r.skill_id.toLowerCase().includes(search.toLowerCase())
    )
  }, [skillDemand.data, search])

  const columns = [
    { key: 'skill_name', label: 'Skill', render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { key: 'distinct_job_count', label: 'Jobs', align: 'right' },
    { key: 'mention_count', label: 'Mentions', align: 'right' },
    { key: 'normalized_distinct_job_count', label: 'Share', align: 'right',
      render: (v: number) => `${(v * 100).toFixed(2)}%` },
    { key: 'confidence', label: 'Confidence', align: 'right',
      render: (v: Record<string, number>) => (
        <span style={{ fontSize: 12 }}>
          <span style={{ color: C.green }}>{v.HIGH || 0}H</span>{' '}
          <span style={{ color: C.gold }}>{v.MEDIUM || 0}M</span>{' '}
          <span style={{ color: C.gray }}>{v.LOW || 0}L</span>
        </span>
      )},
    { key: 'evidence_type_breakdown', label: 'Evidence', align: 'right',
      render: (v: Record<string, number>) => (
        <span style={{ fontSize: 11, color: C.gray }}>
          T:{v.TITLE || 0} D:{v.DESCRIPTION || 0} S:{v.SOURCE_SKILL || 0}
        </span>
      )},
    { key: 'verification_status', label: 'Status',
      render: (v: string) => <Badge status={v} size="sm" /> },
  ]

  return (
    <>
      <Card title={`Skill Intelligence — ${skillDemand.data?.total_jobs_evaluated?.toLocaleString() || '—'} jobs analyzed`}
        right={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="text" placeholder="Search skills…" value={search} onChange={e => setSearch(e.target.value)}
              style={{ padding: '6px 12px', border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 13, width: 200 }} />
          </div>
        }>
        <DataTable columns={columns} rows={rows} onRowClick={setSelectedSkill} />
        <Provenance>
          Shares are normalized distinct-job counts of evidence, NOT weighted demand scores.
          {skillDemand.data ? ` Run: ${skillDemand.data.run_id.slice(0, 16)}…` : ''}
        </Provenance>
      </Card>

      {/* Skill detail drawer */}
      <EvidenceDrawer open={!!selectedSkill} onClose={() => setSelectedSkill(null)}>
        {selectedSkill && (
          <div>
            <h2 style={{ margin: '0 0 16px', fontSize: 18, color: C.dark }}>{selectedSkill.skill_name}</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
              <KPICard label="Distinct Jobs" value={selectedSkill.distinct_job_count} color={C.navy} />
              <KPICard label="Mentions" value={selectedSkill.mention_count} color={C.teal} />
              <KPICard label="Share" value={`${(selectedSkill.normalized_distinct_job_count * 100).toFixed(2)}%`} color={C.gold} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: C.gray }}>STATUS</span>
                <Badge status={selectedSkill.verification_status} />
              </div>
            </div>

            <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Evidence Breakdown</h4>
            <div style={{ fontSize: 13, lineHeight: 1.8, marginBottom: 16 }}>
              <div>Job Title matches: <strong>{selectedSkill.evidence_type_breakdown.TITLE || 0}</strong></div>
              <div>Description matches: <strong>{selectedSkill.evidence_type_breakdown.DESCRIPTION || 0}</strong></div>
              <div>Source skill mentions: <strong>{selectedSkill.evidence_type_breakdown.SOURCE_SKILL || 0}</strong></div>
            </div>

            <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Confidence Distribution</h4>
            <div style={{ fontSize: 13, lineHeight: 1.8, marginBottom: 16 }}>
              <div>HIGH: <strong style={{ color: C.green }}>{selectedSkill.confidence.HIGH || 0}</strong></div>
              <div>MEDIUM: <strong style={{ color: C.gold }}>{selectedSkill.confidence.MEDIUM || 0}</strong></div>
              <div>LOW: <strong style={{ color: C.gray }}>{selectedSkill.confidence.LOW || 0}</strong></div>
            </div>

            <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Data Provenance</h4>
            <div style={{ fontSize: 12, color: C.darkSubtle, lineHeight: 1.7 }}>
              <div>Source: <code>naukri-historical-promptcloud</code></div>
              <div>Freshness: <Badge status="HISTORICAL" size="sm" /></div>
              <div>Method: deterministic skill extraction (canonical matcher)</div>
              <div>Rule version: mvp-v1-no-score</div>
              <div>Verification: {selectedSkill.verification_status}</div>
            </div>
          </div>
        )}
      </EvidenceDrawer>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Skill Gap Explorer
// ═══════════════════════════════════════════════════════════════════════════════

function SkillGapsPage({ district, sector }: { district: string; sector: string }) {
  const q = `?source_id=naukri-historical-promptcloud${district ? `&district=${district}` : ''}${sector ? `&sector=${sector}` : ''}`
  const gaps = useFetch<GapResponse>(`/api/v1/skills/gaps${q}`)
  const [filter, setFilter] = useState('ALL')
  const [selected, setSelected] = useState<GapRow | null>(null)

  const rows = useMemo(() => {
    if (!gaps.data) return []
    if (filter === 'ALL') return gaps.data.rows
    return gaps.data.rows.filter(r => r.gap_status === filter)
  }, [gaps.data, filter])

  const summary = gaps.data?.gap_summary || {}

  const columns = [
    { key: 'skill_name', label: 'Skill', render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { key: 'gap_status', label: 'Gap Status', render: (v: string) => <Badge status={v} /> },
    { key: 'demand_distinct_job_count', label: 'Demand (Jobs)', align: 'right' as const },
    { key: 'demand_mention_count', label: 'Mentions', align: 'right' as const },
    { key: 'has_dvet_supply_evidence', label: 'Supply', align: 'center' as const,
      render: (v: boolean) => v ? <Badge status="VERIFIED" size="sm" /> : <Badge status="NO_DATA" size="sm" /> },
    { key: 'demand_confidence', label: 'Confidence', align: 'right' as const,
      render: (v: Record<string, number>) => (
        <span style={{ fontSize: 12 }}>
          <span style={{ color: C.green }}>{v.HIGH || 0}H</span>{' '}
          <span style={{ color: C.gold }}>{v.MEDIUM || 0}M</span>
        </span>
      )},
  ]

  return (
    <>
      {/* Gap summary cards */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        {[
          ['ALL', C.navy, 'All Skills', (gaps.data?.count || 0)],
          ['HIGH_GAP', C.red, 'High Gap', summary.HIGH_GAP || 0],
          ['MEDIUM_GAP', C.gold, 'Medium Gap', summary.MEDIUM_GAP || 0],
          ['LOW_GAP', C.teal, 'Low Gap', summary.LOW_GAP || 0],
          ['NEEDS_REVIEW', C.gold, 'Needs Review', summary.NEEDS_REVIEW || 0],
          ['NO_DATA', C.gray, 'No Data', summary.NO_DATA || 0],
        ].map(([key, color, label, count]) => (
          <button key={key as string} onClick={() => setFilter(key as string)}
            style={{
              padding: '10px 16px', border: `1px solid ${filter === key ? color : C.border}`,
              borderRadius: 8, background: filter === key ? color : C.white,
              color: filter === key ? C.white : C.dark, cursor: 'pointer',
              fontWeight: filter === key ? 600 : 400, fontSize: 13, minWidth: 100,
              transition: 'all 0.15s',
            }}>
            {label}: <strong>{count}</strong>
          </button>
        ))}
      </div>

      <Card title="Skill Gap Analysis"
        right={<span style={{ fontSize: 12, color: C.gray }}>{rows.length} skills shown</span>}>
        {gaps.loading ? <Loading /> : gaps.error ? <ErrorMsg msg={gaps.error} /> : (
          <>
            <DataTable columns={columns} rows={rows} onRowClick={setSelected} />
            <div style={{ marginTop: 12 }}>
              <Provenance>
                Thresholds: HIGH ≥ {gaps.data?.gap_thresholds?.high_gap_threshold || 0.05} ·
                MEDIUM ≥ {gaps.data?.gap_thresholds?.medium_gap_threshold || 0.01} ·
                Supply: {gaps.data?.dvet_institute_count || 0} institute, {gaps.data?.dvet_trades_total || 0} trades ·
                NOT extrapolated to all of Pune.
              </Provenance>
            </div>
          </>
        )}
      </Card>

      {/* Gap detail drawer */}
      <EvidenceDrawer open={!!selected} onClose={() => setSelected(null)}>
        {selected && (
          <div>
            <h2 style={{ margin: '0 0 8px', fontSize: 18, color: C.dark }}>{selected.skill_name}</h2>
            <Badge status={selected.gap_status} />
            <div style={{ marginTop: 16 }}>
              <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Demand Evidence</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                <KPICard label="Jobs" value={selected.demand_distinct_job_count} color={C.navy} />
                <KPICard label="Mentions" value={selected.demand_mention_count} color={C.teal} />
                <KPICard label="Share" value={`${(selected.demand_normalized_distinct_job_count * 100).toFixed(2)}%`} />
                <KPICard label="Supply" value={selected.has_dvet_supply_evidence ? 'Present' : 'None'}
                  color={selected.has_dvet_supply_evidence ? C.green : C.red} />
              </div>
            </div>

            {selected.has_dvet_supply_evidence && selected.dvet_supply_detail && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>DVET Supply</h4>
                <div style={{ fontSize: 13, lineHeight: 1.8 }}>
                  <div>Trades: {selected.dvet_supply_detail.trades?.join(', ')}</div>
                  <div>Verification: <Badge status="NEEDS_REVIEW" size="sm" /></div>
                </div>
              </div>
            )}

            <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Gap Explanation</h4>
            <div style={{ fontSize: 13, lineHeight: 1.7, color: C.darkSubtle, padding: 12,
              background: C.lightBg, borderRadius: 6, marginBottom: 16 }}>
              {selected.gap_status === 'HIGH_GAP' && !selected.has_dvet_supply_evidence &&
                `High demand (${selected.demand_distinct_job_count} jobs) with NO training supply evidence. This represents a critical skills gap.`}
              {selected.gap_status === 'HIGH_GAP' && selected.has_dvet_supply_evidence &&
                `High demand but supply is flagged NEEDS_REVIEW. Existing training programmes may not adequately cover this skill.`}
              {selected.gap_status === 'MEDIUM_GAP' &&
                `Moderate demand (${selected.demand_distinct_job_count} jobs). Training capacity should be reviewed.`}
              {selected.gap_status === 'LOW_GAP' &&
                `Low but present demand. Monitor trend before acting.`}
              {selected.gap_status === 'NEEDS_REVIEW' &&
                `DVET supply evidence exists but is unverified. Cross-reference with actual intake records.`}
              {selected.gap_status === 'NO_DATA' &&
                `Insufficient data. Add to next ingestion batch.`}
            </div>

            <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 8 }}>Data Source</h4>
            <div style={{ fontSize: 12, color: C.darkSubtle, lineHeight: 1.7 }}>
              <div>Source: naukri-historical-promptcloud</div>
              <div>Freshness: <Badge status="HISTORICAL" size="sm" /></div>
              <div>Method: deterministic skill extraction</div>
            </div>
          </div>
        )}
      </EvidenceDrawer>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Training Supply
// ═══════════════════════════════════════════════════════════════════════════════

function TrainingPage() {
  const supply = useFetch<{ dvet_supply_summary: DvetSupply }>('/api/v1/skills/supply')
  const s = supply.data?.dvet_supply_summary

  return (
    <>
      <Card title="DVET Training Supply — ITI Haveli, Pune">
        {supply.loading ? <Loading /> : !s ? <Empty msg="No supply data." /> : (
          <div>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 16 }}>
              <KPICard label="Institute" value={s.institute_name || '—'} icon="🏫" />
              <KPICard label="Trades" value={s.total_trades} icon="🔧" color={C.teal} />
              <KPICard label="Total Intake" value={s.total_intake} icon="👥" color={C.navy} />
              <KPICard label="Skills Covered" value={Object.keys(s.skills_with_supply_evidence || {}).length}
                icon="🎯" color={C.gold} />
            </div>

            <Provenance>{s.extrapolation_note}</Provenance>

            {s.skills_with_supply_evidence && Object.keys(s.skills_with_supply_evidence).length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 10 }}>Skills with Supply Evidence</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: `2px solid ${C.border}` }}>
                        <th style={{ padding: '8px 10px', textAlign: 'left' }}>Skill ID</th>
                        <th style={{ padding: '8px 10px', textAlign: 'left' }}>Covering Trades</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Trade Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(s.skills_with_supply_evidence).map(([sid, detail]) => (
                        <tr key={sid} style={{ borderBottom: `1px solid ${C.borderLight}` }}>
                          <td style={{ padding: '7px 10px', fontWeight: 500 }}>{sid}</td>
                          <td style={{ padding: '7px 10px', fontSize: 12 }}>{(detail as any).trades?.join(', ')}</td>
                          <td style={{ padding: '7px 10px', textAlign: 'right' }}>{(detail as any).count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {s.occupations_with_supply_evidence && Object.keys(s.occupations_with_supply_evidence).length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h4 style={{ fontSize: 13, color: C.gray, marginBottom: 10 }}>Occupations with Supply Evidence</h4>
                <div style={{ fontSize: 13 }}>
                  {Object.entries(s.occupations_with_supply_evidence).map(([occ, detail]) => (
                    <div key={occ} style={{ marginBottom: 4 }}>
                      <strong>{occ}</strong>: {(detail as any).trades?.join(', ')}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Recommendations
// ═══════════════════════════════════════════════════════════════════════════════

function RecommendationsPage({ district, sector }: { district: string; sector: string }) {
  const q = `?source_id=naukri-historical-promptcloud${district ? `&district=${district}` : ''}${sector ? `&sector=${sector}` : ''}`
  const recs = useFetch<RecommendationsResponse>(`/api/v1/skills/recommendations${q}&limit=20`)

  const priorityColor: Record<string, string> = { HIGH: C.red, MEDIUM: C.gold, LOW: C.gray }

  return (
    <>
      <Card title="Deterministic Skill Recommendations"
        right={<Badge status={recs.data?.rule_version || 'loading'} size="sm" />}>
        {recs.loading ? <Loading /> : recs.error ? <ErrorMsg msg={recs.error} /> : (
          <div>
            {recs.data && recs.data.recommendations.length === 0 && (
              <Empty msg="No recommendations — insufficient data under current filters." />
            )}
            {(recs.data?.recommendations || []).map((r, i) => (
              <div key={i} style={{
                padding: '16px 18px', border: `1px solid ${C.border}`, borderRadius: 8,
                marginBottom: 12, borderLeft: `4px solid ${priorityColor[r.priority] || C.gray}`,
                background: C.white,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <div>
                    <strong style={{ fontSize: 14, color: C.dark }}>{r.skill_name}</strong>
                    <div style={{ marginTop: 4, fontSize: 13, color: C.darkSubtle }}>{r.recommendation}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Badge status={r.priority} />
                    <Badge status={r.data_quality} size="sm" />
                  </div>
                </div>
                <div style={{ fontSize: 12, color: C.gray, lineHeight: 1.7, marginTop: 8 }}>
                  <div><strong>Reason:</strong> {r.reason}</div>
                  <div><strong>Evidence:</strong> {r.evidence}</div>
                  <div><strong>Next action:</strong> {r.next_action}</div>
                </div>
              </div>
            ))}
            <Provenance>
              {recs.data?.note || 'Recommendations are deterministic rules applied to verified evidence.'}
            </Provenance>
          </div>
        )}
      </Card>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Page: Q&A Assistant
// ═══════════════════════════════════════════════════════════════════════════════

function AssistantPage() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<RAGResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = useCallback(() => {
    if (!query.trim()) return
    setLoading(true); setError(null)
    fetch(`/api/v1/ai/ask?q=${encodeURIComponent(query.trim())}`)
      .then(r => r.json())
      .then(d => {
        const ai = d.ai || {}
        const rag = d.rag || {}
        setResult({ ...ai, evidence: rag.evidence || ai.evidence || [] })
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [query])

  const presets = [
    'What are the top skills in Pune IT-ITeS?',
    'Which skills have the largest observed gaps?',
    'What training trades cover Python?',
    'How many jobs have district evidence?',
  ]

  return (
    <Card title="Labour-Market Assistant (Evidence-Grounded)">
      <p style={{ fontSize: 13, color: C.gray, marginBottom: 12, lineHeight: 1.5 }}>
        Ask about the Maharashtra labour market. Answers come from persisted observations only — no fabricated statistics.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <input type="text" value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ask()}
          placeholder="Ask a question…"
          style={{ flex: 1, padding: '10px 14px', border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 14 }} />
        <button onClick={ask} disabled={loading || !query.trim()}
          style={{ padding: '10px 20px', backgroundColor: C.navy, color: C.white, border: 'none',
            borderRadius: 6, fontWeight: 600, cursor: loading ? 'wait' : 'pointer', fontSize: 14,
            opacity: loading || !query.trim() ? 0.6 : 1 }}>
          {loading ? 'Searching…' : 'Ask'}
        </button>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
        {presets.map(p => (
          <button key={p} onClick={() => setQuery(p)}
            style={{ padding: '4px 10px', border: `1px solid ${C.border}`, borderRadius: 12,
              backgroundColor: C.lightBg, fontSize: 11, color: C.navy, cursor: 'pointer' }}>
            {p}
          </button>
        ))}
      </div>
      {error && <ErrorMsg msg={error} />}
      {result && (
        <div style={{ backgroundColor: C.lightBg, borderRadius: 8, padding: 20 }}>
          <div style={{ fontSize: 14, lineHeight: 1.7, color: C.dark, marginBottom: 12 }}>{result.answer}</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: C.gray }}>Confidence: <strong>{result.confidence}</strong></span>
            <span style={{ fontSize: 12, color: C.gray }}>Evidence: <strong>{result.evidence_count}</strong> records</span>
            <span style={{ fontSize: 12, color: C.gray }}>Freshness: <Badge status={result.source_freshness} /></span>
          </div>
          {result.evidence && result.evidence.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ fontSize: 12, color: C.navy, cursor: 'pointer' }}>Evidence ({result.evidence.length})</summary>
              <div style={{ marginTop: 8, fontSize: 12 }}>
                {result.evidence.map((e, i) => (
                  <div key={i} style={{ marginBottom: 6, padding: '6px 10px', backgroundColor: C.white,
                    borderRadius: 4, border: `1px solid ${C.border}` }}>
                    <span style={{ fontWeight: 500 }}>[{e.type}]</span> {e.title}
                    {e.snippet && <span style={{ color: C.gray }}> — {e.snippet.slice(0, 100)}…</span>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {result.disclaimer && (
            <div style={{ marginTop: 10, padding: '6px 12px', backgroundColor: '#FFFFF0',
              border: '1px solid #ECC94B', borderRadius: 4, fontSize: 11, color: '#975A16' }}>
              {result.disclaimer}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sidebar navigation
// ═══════════════════════════════════════════════════════════════════════════════

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'skills', label: 'Skill Intelligence', icon: '🎯' },
  { id: 'gaps', label: 'Skill Gap Explorer', icon: '⚠️' },
  { id: 'training', label: 'Training Supply', icon: '🏫' },
  { id: 'recommendations', label: 'Recommendations', icon: '💡' },
  { id: 'assistant', label: 'AI Assistant', icon: '🤖' },
] as const

// ═══════════════════════════════════════════════════════════════════════════════
// Main App
// ═══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [district, setDistrict] = useState('Pune')
  const [sector, setSector] = useState('IT-ITeS')

  const activeItem = NAV.find(n => n.id === page)

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: C.bg, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      {/* Sidebar */}
      <aside style={{
        width: C.sidebarW, minWidth: C.sidebarW, backgroundColor: C.navyDark,
        color: C.white, display: 'flex', flexDirection: 'column',
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 18px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ fontSize: 10, letterSpacing: 1, textTransform: 'uppercase', opacity: 0.6, marginBottom: 4 }}>
            Government of Maharashtra
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1.2 }}>
            Demand<span style={{ color: C.teal }}>-X</span>
          </div>
          <div style={{ fontSize: 11, opacity: 0.5, marginTop: 2 }}>
            Labour Market Intelligence
          </div>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, padding: '12px 0' }}>
          {NAV.map(item => (
            <button key={item.id} onClick={() => setPage(item.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                padding: '10px 18px', border: 'none', cursor: 'pointer',
                background: page === item.id ? 'rgba(255,255,255,0.1)' : 'transparent',
                color: C.white, fontSize: 13, textAlign: 'left',
                borderLeft: page === item.id ? `3px solid ${C.teal}` : '3px solid transparent',
                fontWeight: page === item.id ? 600 : 400,
                transition: 'background 0.12s',
              }}
              onMouseEnter={e => { if (page !== item.id) (e.target as HTMLElement).style.background = 'rgba(255,255,255,0.05)' }}
              onMouseLeave={e => { if (page !== item.id) (e.target as HTMLElement).style.background = 'transparent' }}
            >
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Pilot badge */}
        <div style={{ padding: '14px 18px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ fontSize: 10, letterSpacing: 0.5, textTransform: 'uppercase', opacity: 0.5, marginBottom: 4 }}>
            Pilot
          </div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Maharashtra · Pune</div>
          <div style={{ fontSize: 10, opacity: 0.5, marginTop: 2 }}>September 2026</div>
        </div>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top bar */}
        <header style={{
          backgroundColor: C.white, borderBottom: `1px solid ${C.border}`,
          padding: '14px 28px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: C.dark }}>{activeItem?.icon} {activeItem?.label}</div>
            <div style={{ fontSize: 12, color: C.gray, marginTop: 2 }}>
              Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform
            </div>
          </div>
          <FilterBar district={district} setDistrict={setDistrict} sector={sector} setSector={setSector} />
        </header>

        {/* Page content */}
        <main style={{ flex: 1, padding: '24px 28px', maxWidth: 1200, width: '100%', boxSizing: 'border-box' }}>
          {page === 'dashboard' && <DashboardPage district={district} sector={sector} />}
          {page === 'skills' && <SkillsPage district={district} sector={sector} />}
          {page === 'gaps' && <SkillGapsPage district={district} sector={sector} />}
          {page === 'training' && <TrainingPage />}
          {page === 'recommendations' && <RecommendationsPage district={district} sector={sector} />}
          {page === 'assistant' && <AssistantPage />}
        </main>

        {/* Footer */}
        <footer style={{
          borderTop: `1px solid ${C.border}`, padding: '12px 28px',
          backgroundColor: C.white, color: C.gray, fontSize: 11,
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>Department of Skills, Employment, Entrepreneurship and Innovation</span>
          <span>Pune Pilot · Evidence-Grounding Enforced · v0.5</span>
        </footer>
      </div>
    </div>
  )
}
