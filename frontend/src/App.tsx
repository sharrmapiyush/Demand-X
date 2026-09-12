import React, { useState, useEffect, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'

// ─── Types ────────────────────────────────────────────────────────────────────

interface HealthResponse {
  status: string
  app_name: string
  environment: string
  database: string
  pilot_district: string
  sectors: string[]
}

interface JobStats {
  total: number
  with_district: number
  without_district: number
  by_district: Record<string, number>
  by_source: Record<string, number>
}

interface SkillDemandRow {
  skill_id: string
  skill_name: string
  distinct_job_count: number
  mention_count: number
  normalized_distinct_job_count: number
  confidence: Record<string, number>
  evidence_type_breakdown: Record<string, number>
  verification_status: string
}

interface SkillDemandResponse {
  rows: SkillDemandRow[]
  total_jobs_evaluated: number
  jobs_with_skill_evidence: number
  skills_with_evidence: number
  total_evidence_rows: number
  source_id: string
  run_id: string
}

interface DistrictDemandRow {
  id: string
  district: string
  occupation_id: string
  job_count: number
  apprenticeship_count: number
  demand_score: number | null
  data_completeness_status: string
  rule_version: string
}

interface SourcePolicy {
  source_id: string
  source_name: string
  source_category: string
  authorization_status: string
  robots_status: string
  enabled: boolean
}

interface SourceHealth {
  source_id: string
  source_name: string
  status: string
  last_fetched_at: string | null
  freshness_class: string
  reliability_notes: string | null
}

interface DvetSupply {
  skills_with_supply: Record<string, string[]>
  trades_count: number
  skills_count: number
  note: string
}

interface RAGResponse {
  answer: string
  confidence: string
  evidence_count: number
  source_freshness: string
  disclaimer: string
  evidence: Array<{ type: string; id: string; title: string; snippet: string }>
}

// ─── Color palette ────────────────────────────────────────────────────────────

const COLORS = {
  navy: '#0B3D66',
  teal: '#0E7C7B',
  gold: '#C9960C',
  green: '#1E8E5A',
  red: '#C53030',
  blue: '#3182CE',
  gray: '#5B6B79',
  lightBg: '#F0F4F8',
  border: '#DCE3E8',
  white: '#FFFFFF',
  darkText: '#1A2733',
}
const PIE_COLORS = ['#0B3D66', '#0E7C7B', '#C9960C', '#3182CE', '#1E8E5A', '#805AD5', '#DD6B20', '#E53E3E']

// ─── Fetch hook ───────────────────────────────────────────────────────────────

function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [url])

  return { data, loading, error }
}

// ─── Shared components ────────────────────────────────────────────────────────

function Card({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div style={{
      backgroundColor: COLORS.white, borderRadius: 8, border: `1px solid ${COLORS.border}`,
      padding: '20px 24px', marginBottom: 20, ...(className ? {} : {}),
    }}>
      {title && <h3 style={{ margin: '0 0 12px 0', fontSize: 15, color: COLORS.darkText, fontWeight: 600 }}>{title}</h3>}
      {children}
    </div>
  )
}

function KPICard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      padding: '16px 20px', border: `1px solid ${COLORS.border}`, borderRadius: 6,
      backgroundColor: COLORS.white, minWidth: 180,
    }}>
      <div style={{ fontSize: 11, color: COLORS.gray, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: color || COLORS.darkText, marginTop: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: COLORS.gray, marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    ONLINE: COLORS.green, DEGRADED: COLORS.gold, OFFLINE: COLORS.red, BLOCKED: COLORS.red,
    HISTORICAL: COLORS.gray, PERIODIC: COLORS.teal, LIVE: COLORS.green, STATIC: COLORS.gray,
    NEEDS_REVIEW: COLORS.gold, VERIFIED: COLORS.green,
  }
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 11, fontWeight: 600, color: COLORS.white,
      backgroundColor: colorMap[status] || COLORS.gray,
    }}>{status}</span>
  )
}

function ProvenanceNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'inline-block', padding: '5px 12px', backgroundColor: COLORS.lightBg,
      border: `1px solid ${COLORS.border}`, borderRadius: 4, fontSize: 11, color: COLORS.gray,
      fontFamily: 'monospace', marginTop: 8,
    }}>
      {children}
    </div>
  )
}

// ─── Tab: Overview ────────────────────────────────────────────────────────────

function OverviewTab() {
  const health = useFetch<HealthResponse>('/api/v1/health')
  const jobStats = useFetch<JobStats>('/api/v1/jobs/stats')
  const skillDemand = useFetch<SkillDemandResponse>('/api/v1/skills/demand?limit=32')

  const h = health.data
  const js = jobStats.data
  const sd = skillDemand.data

  return (
    <>
      <Card title="System Health">
        {health.loading ? <p style={{ color: COLORS.gray }}>Checking API…</p> :
         health.error ? (
          <div style={{ padding: 12, backgroundColor: '#FFF5F5', border: '1px solid #FEB2B2', borderRadius: 6, color: '#9B2C2C', fontSize: 13 }}>
            API unreachable: {health.error}
          </div>
        ) : h && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <KPICard label="API Status" value={h.status.toUpperCase()} color={h.status === 'healthy' ? COLORS.green : COLORS.gold} />
            <KPICard label="Database" value={h.database} color={h.database === 'healthy' ? COLORS.green : COLORS.red} />
            <KPICard label="Pilot District" value={h.pilot_district} />
            <KPICard label="Environment" value={h.environment} />
          </div>
        )}
      </Card>

      <Card title="Data Summary">
        {jobStats.loading ? <p style={{ color: COLORS.gray }}>Loading…</p> :
         jobStats.error ? <p style={{ color: COLORS.red }}>Error: {jobStats.error}</p> :
         js && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
            <KPICard label="Total Job Postings" value={js.total.toLocaleString()} color={COLORS.navy} />
            <KPICard label="With District" value={js.with_district.toLocaleString()} color={COLORS.teal} />
            <KPICard label="Without District" value={js.without_district.toLocaleString()} color={COLORS.gold} />
            <KPICard label="Districts w/ Data" value={Object.keys(js.by_district).length} />
            <KPICard label="Canonical Skills Hit" value={sd ? sd.skills_with_evidence : '—'} color={COLORS.green} />
          </div>
        )}
        <ProvenanceNote>Verified Rule: No synthetic data. All counts are from real persisted observations.</ProvenanceNote>
      </Card>

      {js && Object.keys(js.by_source).length > 0 && (
        <Card title="Jobs by Source">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(js.by_source).map(([src, cnt]) => (
              <div key={src} style={{ padding: '8px 14px', border: `1px solid ${COLORS.border}`, borderRadius: 6, fontSize: 13 }}>
                <span style={{ color: COLORS.gray }}>{src}:</span> <strong>{cnt.toLocaleString()}</strong>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  )
}

// ─── Tab: Demand ──────────────────────────────────────────────────────────────

function DemandTab() {
  const demand = useFetch<{ rows: DistrictDemandRow[]; count: number }>('/api/v1/districts/demand?limit=100')
  const jobStats = useFetch<JobStats>('/api/v1/jobs/stats')

  const districtChart = React.useMemo(() => {
    if (!jobStats.data) return []
    return Object.entries(jobStats.data.by_district)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([district, count]) => ({ district, jobs: count }))
  }, [jobStats.data])

  const occupationChart = React.useMemo(() => {
    if (!demand.data) return []
    const occCounts: Record<string, number> = {}
    for (const row of demand.data.rows) {
      occCounts[row.occupation_id] = (occCounts[row.occupation_id] || 0) + row.job_count
    }
    return Object.entries(occCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, value]) => ({ name, value }))
  }, [demand.data])

  return (
    <>
      <Card title="Job Distribution by District">
        {jobStats.loading ? <p style={{ color: COLORS.gray }}>Loading…</p> : districtChart.length === 0 ? (
          <p style={{ color: COLORS.gray }}>No district data available.</p>
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={districtChart} margin={{ top: 5, right: 20, bottom: 25, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
              <XAxis dataKey="district" angle={-35} textAnchor="end" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="jobs" fill={COLORS.navy} name="Job Postings" />
            </BarChart>
          </ResponsiveContainer>
        )}
        <ProvenanceNote>District counts from persisted job_postings. {jobStats.data?.without_district || 0} jobs have no district evidence.</ProvenanceNote>
      </Card>

      {occupationChart.length > 0 && (
        <Card title="Occupation Demand Distribution">
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie data={occupationChart} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={120} label={({ name, value }) => `${name}: ${value}`}>
                {occupationChart.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      )}

      {demand.data && demand.data.rows.length > 0 && (
        <Card title={`District Occupation Demand (${demand.data.count} rows)`}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${COLORS.border}`, textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px' }}>District</th>
                  <th style={{ padding: '8px 10px' }}>Occupation</th>
                  <th style={{ padding: '8px 10px', textAlign: 'right' }}>Job Count</th>
                  <th style={{ padding: '8px 10px', textAlign: 'right' }}>Apprenticeships</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 10px' }}>Rule Version</th>
                </tr>
              </thead>
              <tbody>
                {demand.data.rows.slice(0, 30).map((r, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <td style={{ padding: '6px 10px' }}>{r.district}</td>
                    <td style={{ padding: '6px 10px' }}>{r.occupation_id}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600 }}>{r.job_count}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>{r.apprenticeship_count}</td>
                    <td style={{ padding: '6px 10px' }}><StatusBadge status={r.data_completeness_status} /></td>
                    <td style={{ padding: '6px 10px', fontSize: 11, color: COLORS.gray }}>{r.rule_version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  )
}

// ─── Tab: Skill Gaps ─────────────────────────────────────────────────────────

function SkillGapsTab() {
  const skillDemand = useFetch<SkillDemandResponse>('/api/v1/skills/demand?limit=32')
  const dvetSupply = useFetch<{ dvet_supply_summary: DvetSupply; note: string }>('/api/v1/skills/supply')

  const skillChart = React.useMemo(() => {
    if (!skillDemand.data) return []
    return skillDemand.data.rows
      .filter(r => r.distinct_job_count > 0)
      .slice(0, 16)
      .map(r => ({
        name: r.skill_name.length > 22 ? r.skill_name.slice(0, 20) + '…' : r.skill_name,
        fullName: r.skill_name,
        distinct_jobs: r.distinct_job_count,
        mentions: r.mention_count,
        share: (r.normalized_distinct_job_count * 100).toFixed(2) + '%',
        high: r.confidence.HIGH || 0,
        medium: r.confidence.MEDIUM || 0,
        low: r.confidence.LOW || 0,
        verified: r.verification_status,
      }))
  }, [skillDemand.data])

  const supply = dvetSupply.data?.dvet_supply_summary

  return (
    <>
      <Card title="Skill Demand Ranking (Canonical 32)">
        {skillDemand.loading ? <p style={{ color: COLORS.gray }}>Loading…</p> : skillChart.length === 0 ? (
          <p style={{ color: COLORS.gray }}>No skill demand evidence found.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(320, skillChart.length * 28)}>
            <BarChart data={skillChart} layout="vertical" margin={{ top: 5, right: 40, bottom: 5, left: 160 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.border} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={155} />
              <Tooltip />
              <Bar dataKey="distinct_jobs" fill={COLORS.teal} name="Distinct Jobs" />
            </BarChart>
          </ResponsiveContainer>
        )}
        <ProvenanceNote>
          {skillDemand.data
            ? `${skillDemand.data.jobs_with_skill_evidence} of ${skillDemand.data.total_jobs_evaluated} jobs carry evidence · run ${skillDemand.data.run_id.slice(0, 12)}…`
            : 'Evidence computed from persisted job_postings via canonical matcher.'}
        </ProvenanceNote>
      </Card>

      {skillDemand.data && (
        <Card title="Skill Evidence Details">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${COLORS.border}`, textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px' }}>Skill</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>Distinct Jobs</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>Mentions</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>Share</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>HIGH</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>MED</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>LOW</th>
                  <th style={{ padding: '6px 8px' }}>Title</th>
                  <th style={{ padding: '6px 8px' }}>Desc</th>
                  <th style={{ padding: '6px 8px' }}>Source</th>
                  <th style={{ padding: '6px 8px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {skillDemand.data.rows.filter(r => r.distinct_job_count > 0).slice(0, 32).map((r, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <td style={{ padding: '5px 8px', fontWeight: 500 }}>{r.skill_name}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{r.distinct_job_count}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{r.mention_count}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{(r.normalized_distinct_job_count * 100).toFixed(2)}%</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: COLORS.green }}>{r.confidence.HIGH || 0}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: COLORS.gold }}>{r.confidence.MEDIUM || 0}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: COLORS.gray }}>{r.confidence.LOW || 0}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{r.evidence_type_breakdown.TITLE || 0}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{r.evidence_type_breakdown.DESCRIPTION || 0}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right' }}>{r.evidence_type_breakdown.SOURCE_SKILL || 0}</td>
                    <td style={{ padding: '5px 8px' }}><StatusBadge status={r.verification_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="DVET Supply Coverage (Read-Only Snapshot)">
        {dvetSupply.loading ? <p style={{ color: COLORS.gray }}>Loading…</p> :
         supply ? (
          <div>
            <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
              <KPICard label="Trades in Snapshot" value={supply.trades_count || 0} />
              <KPICard label="Skills with Supply" value={supply.skills_count || 0} color={COLORS.teal} />
            </div>
            {supply.skills_with_supply && Object.keys(supply.skills_with_supply).length > 0 && (
              <div style={{ fontSize: 13 }}>
                {Object.entries(supply.skills_with_supply).map(([skillId, trades]) => (
                  <div key={skillId} style={{ marginBottom: 4 }}>
                    <strong>{skillId}</strong>: {trades.join(', ')}
                  </div>
                ))}
              </div>
            )}
            <ProvenanceNote>{supply.note || 'DVET snapshot covers a single institute; supply is NOT extrapolated district-wide.'}</ProvenanceNote>
          </div>
        ) : <p style={{ color: COLORS.gray }}>No DVET supply data available.</p>}
      </Card>

      <Card title="Velocity (Honest Status)">
        <p style={{ fontSize: 13, color: COLORS.gray, lineHeight: 1.6 }}>
          Skill velocity requires ≥2 observation windows from distinct ingestion runs.
          Current evidence is a single static historical snapshot — all skills are labeled
          <strong> INSUFFICIENT_DATA</strong> or <strong>STATIC_SNAPSHOT</strong>.
          No rising/falling trend is claimed.
        </p>
        <ProvenanceNote>Verified Rule: Historical source is NOT presented as live velocity.</ProvenanceNote>
      </Card>
    </>
  )
}

// ─── Tab: Recommendations (RAG Q&A) ──────────────────────────────────────────

function RecommendationsTab() {
  const [query, setQuery] = useState('')
  const [ragResult, setRagResult] = useState<RAGResponse | null>(null)
  const [ragLoading, setRagLoading] = useState(false)
  const [ragError, setRagError] = useState<string | null>(null)

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return
    setRagLoading(true)
    setRagError(null)
    const q = query.trim()
    fetch(`/api/v1/ai/ask?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(d => { setRagResult(d.ai || d.rag); setRagLoading(false) })
      .catch(e => { setRagError(e.message); setRagLoading(false) })
  }, [query])

  const presets = [
    'What skills are most in demand in Pune?',
    'Which occupation has the most job postings?',
    'What is the DVET supply coverage for IT skills?',
    'How many jobs have district evidence?',
  ]

  return (
    <>
      <Card title="Labour-Market Q&A (Evidence-Grounded)">
        <p style={{ fontSize: 13, color: COLORS.gray, marginBottom: 12, lineHeight: 1.5 }}>
          Ask a question about the Maharashtra labour market. Answers are grounded in persisted observations
          only — no fabricated statistics, no invented salary data, no government impersonation.
        </p>

        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            placeholder="Ask a question…"
            style={{
              flex: 1, padding: '10px 14px', border: `1px solid ${COLORS.border}`, borderRadius: 6,
              fontSize: 14, outline: 'none',
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={ragLoading || !query.trim()}
            style={{
              padding: '10px 20px', backgroundColor: COLORS.navy, color: COLORS.white,
              border: 'none', borderRadius: 6, cursor: ragLoading ? 'wait' : 'pointer',
              fontWeight: 600, fontSize: 14, opacity: ragLoading || !query.trim() ? 0.6 : 1,
            }}
          >
            {ragLoading ? 'Searching…' : 'Ask'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
          {presets.map(p => (
            <button
              key={p}
              onClick={() => { setQuery(p); }}
              style={{
                padding: '4px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 12,
                backgroundColor: COLORS.lightBg, fontSize: 11, color: COLORS.navy,
                cursor: 'pointer',
              }}
            >{p}</button>
          ))}
        </div>

        {ragError && (
          <div style={{ padding: 12, backgroundColor: '#FFF5F5', border: '1px solid #FEB2B2', borderRadius: 6, color: '#9B2C2C', fontSize: 13, marginBottom: 12 }}>
            Error: {ragError}
          </div>
        )}

        {ragResult && (
          <div style={{ backgroundColor: COLORS.lightBg, borderRadius: 8, padding: 20 }}>
            <div style={{ fontSize: 14, lineHeight: 1.7, color: COLORS.darkText, marginBottom: 12 }}>
              {ragResult.answer}
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: COLORS.gray }}>Confidence: <strong>{ragResult.confidence}</strong></span>
              <span style={{ fontSize: 12, color: COLORS.gray }}>Evidence: <strong>{ragResult.evidence_count}</strong> records</span>
              <span style={{ fontSize: 12, color: COLORS.gray }}>Freshness: <StatusBadge status={ragResult.source_freshness} /></span>
            </div>
            {ragResult.evidence && ragResult.evidence.length > 0 && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ fontSize: 12, color: COLORS.navy, cursor: 'pointer' }}>View Evidence Sources ({ragResult.evidence.length})</summary>
                <div style={{ marginTop: 8, fontSize: 12 }}>
                  {ragResult.evidence.map((e, i) => (
                    <div key={i} style={{ marginBottom: 6, padding: '6px 10px', backgroundColor: COLORS.white, borderRadius: 4, border: `1px solid ${COLORS.border}` }}>
                      <span style={{ fontWeight: 500 }}>[{e.type}]</span> {e.title}
                      {e.snippet && <span style={{ color: COLORS.gray }}> — {e.snippet.slice(0, 100)}…</span>}
                    </div>
                  ))}
                </div>
              </details>
            )}
            {ragResult.disclaimer && (
              <div style={{ marginTop: 10, padding: '6px 12px', backgroundColor: '#FFFFF0', border: '1px solid #ECC94B', borderRadius: 4, fontSize: 11, color: '#975A16' }}>
                {ragResult.disclaimer}
              </div>
            )}
          </div>
        )}
      </Card>
    </>
  )
}

// ─── Tab: Sources ─────────────────────────────────────────────────────────────

function SourcesTab() {
  const policies = useFetch<{ policies: SourcePolicy[]; count: number }>('/api/v1/governance/policies')
  const health = useFetch<{ sources: SourceHealth[]; count: number }>('/api/v1/governance/health')
  const districts = useFetch<{ districts: Array<{ name: string; division: string }>; count: number }>('/api/v1/districts/')

  return (
    <>
      <Card title="Source Governance & Health">
        {health.loading ? <p style={{ color: COLORS.gray }}>Loading…</p> :
         health.error ? <p style={{ color: COLORS.red }}>Error: {health.error}</p> :
         health.data && health.data.sources.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${COLORS.border}`, textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px' }}>Source ID</th>
                  <th style={{ padding: '8px 10px' }}>Name</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                  <th style={{ padding: '8px 10px' }}>Freshness</th>
                  <th style={{ padding: '8px 10px' }}>Last Fetched</th>
                  <th style={{ padding: '8px 10px' }}>Reliability</th>
                </tr>
              </thead>
              <tbody>
                {health.data.sources.map(s => (
                  <tr key={s.source_id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: 12 }}>{s.source_id}</td>
                    <td style={{ padding: '6px 10px' }}>{s.source_name}</td>
                    <td style={{ padding: '6px 10px' }}><StatusBadge status={s.status} /></td>
                    <td style={{ padding: '6px 10px' }}><StatusBadge status={s.freshness_class} /></td>
                    <td style={{ padding: '6px 10px', fontSize: 12 }}>{s.last_fetched_at ? new Date(s.last_fetched_at).toLocaleDateString() : 'Never'}</td>
                    <td style={{ padding: '6px 10px', fontSize: 11, color: COLORS.gray, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {s.reliability_notes || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p style={{ color: COLORS.gray }}>No source data available.</p>}
        <ProvenanceNote>Health telemetry is from persisted Source registry — not fabricated.</ProvenanceNote>
      </Card>

      {policies.data && policies.data.policies.length > 0 && (
        <Card title={`Governance Policies (${policies.data.count})`}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${COLORS.border}`, textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px' }}>Source</th>
                  <th style={{ padding: '6px 8px' }}>Category</th>
                  <th style={{ padding: '6px 8px' }}>Authorization</th>
                  <th style={{ padding: '6px 8px' }}>Robots</th>
                  <th style={{ padding: '6px 8px' }}>Enabled</th>
                </tr>
              </thead>
              <tbody>
                {policies.data.policies.slice(0, 20).map(p => (
                  <tr key={p.source_id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: 12 }}>{p.source_id}</td>
                    <td style={{ padding: '5px 8px' }}>{p.source_category}</td>
                    <td style={{ padding: '5px 8px' }}><StatusBadge status={p.authorization_status} /></td>
                    <td style={{ padding: '5px 8px' }}><StatusBadge status={p.robots_status} /></td>
                    <td style={{ padding: '5px 8px' }}>{p.enabled ? '✓' : '✗'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {districts.data && (
        <Card title={`Maharashtra Geography — ${districts.data.count} Districts`}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {districts.data.districts.map(d => (
              <div key={d.name} style={{
                padding: '5px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 6,
                fontSize: 12, backgroundColor: COLORS.lightBg,
              }}>
                <span style={{ fontWeight: 500 }}>{d.name}</span>
                <span style={{ color: COLORS.gray, marginLeft: 4 }}>({d.division})</span>
              </div>
            ))}
          </div>
          <ProvenanceNote>36 districts across 6 revenue divisions. "Maharashtra" alone resolves to AMBIGUOUS — never defaults to Mumbai.</ProvenanceNote>
        </Card>
      )}
    </>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'demand', label: 'Demand' },
  { id: 'skill-gaps', label: 'Skill Gaps' },
  { id: 'recommendations', label: 'Recommendations' },
  { id: 'sources', label: 'Sources' },
] as const

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('overview')

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#F7F9FC' }}>
      {/* Header */}
      <header style={{
        backgroundColor: COLORS.navy, color: COLORS.white,
        padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: 0.5, textTransform: 'uppercase', opacity: 0.85 }}>
            Government of Maharashtra · Skill Development, Employment, Entrepreneurship & Innovation
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: 19, fontWeight: 600 }}>
            Labour-Market Intelligence & Curriculum-Alignment Platform
          </h1>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ fontSize: 12, backgroundColor: 'rgba(255,255,255,0.15)', padding: '4px 10px', borderRadius: 4 }}>
            Pilot: <strong>Pune</strong>
          </span>
          <span style={{ fontSize: 12, backgroundColor: COLORS.teal, padding: '4px 10px', borderRadius: 4 }}>
            v0.4 Intelligence
          </span>
        </div>
      </header>

      {/* Navigation */}
      <nav style={{
        backgroundColor: COLORS.white, borderBottom: `1px solid ${COLORS.border}`,
        padding: '0 24px', display: 'flex', gap: 24,
      }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '14px 4px', border: 'none', background: 'none',
              borderBottom: activeTab === tab.id ? `3px solid ${COLORS.navy}` : '3px solid transparent',
              color: activeTab === tab.id ? COLORS.navy : COLORS.gray,
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer', fontSize: 14,
            }}
          >{tab.label}</button>
        ))}
      </nav>

      {/* Main Content */}
      <main style={{ flex: 1, padding: '28px 24px', maxWidth: 1200, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'demand' && <DemandTab />}
        {activeTab === 'skill-gaps' && <SkillGapsTab />}
        {activeTab === 'recommendations' && <RecommendationsTab />}
        {activeTab === 'sources' && <SourcesTab />}
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: `1px solid ${COLORS.border}`, padding: '14px 24px',
        backgroundColor: COLORS.white, color: COLORS.gray, fontSize: 12, textAlign: 'center',
      }}>
        Department of Skills, Employment, Entrepreneurship and Innovation · Pune Pilot · Evidence-Grounding Enforced · September 2026
      </footer>
    </div>
  )
}