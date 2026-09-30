export const meta = {
  name: 'review-branch',
  description: 'Multi-dimension review of the current branch diff vs a base (default origin/dev) with adversarial verification',
  whenToUse: 'Opt-in deep review of a feature branch before the PR — fans out one reviewer per dimension (correctness, data isolation & authz, payments & secrets, UI states, performance), then tries to refute each finding so only survivors are reported. Complements the mandatory code-reviewer + security-auditor gate; does not replace it.',
  phases: [
    { title: 'Review' },
    { title: 'Verify' },
  ],
}

// Base to diff against — override with args: { base: 'origin/main' }
const BASE = (args && args.base) || 'origin/dev'
const DIFF = `git diff ${BASE}...HEAD`

// One reviewer per dimension: security-auditor for the leak-prone lenses, code-reviewer otherwise.
// Both are the read-only opus reviewers from .claude/agents/.
const DIMENSIONS = [
  { key: 'correctness',     agentType: 'code-reviewer',    focus: 'logic bugs, wrong conditionals, unhandled null/undefined, off-by-one, async/await races, error paths that swallow failures' },
  { key: 'isolation-authz', agentType: 'security-auditor', focus: 'data scoping per CLAUDE.md and .claude/rules/ (a query or write on scoped data missing its scope filter, scope taken from the request body, IDOR), server-side role checks on protected routes and admin pages' },
  { key: 'payments-secrets', agentType: 'security-auditor', focus: 'webhook/callback signature verification, idempotency, amount tampering, secrets read server-side only, input validation at trust boundaries' },
  { key: 'ui-states',       agentType: 'code-reviewer',    focus: 'all UI states handled (loading only when no data yet, error, empty, success), buttons disabled during async, accessible and tappable controls, no silent error swallowing' },
  { key: 'perf',            agentType: 'code-reviewer',    focus: 'N+1 queries or awaits in loops, unbounded list queries without a limit, missing cache/revalidation strategy, client-side fetching that should run on the server' },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'one-sentence defect statement' },
          file: { type: 'string', description: 'repo-relative path' },
          line: { type: 'number', description: '1-indexed line the finding anchors to' },
          failure_scenario: { type: 'string', description: 'concrete inputs/state -> wrong output/leak/crash' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['summary', 'file', 'failure_scenario'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean', description: 'true if the finding is not a real defect in this diff' },
    reason: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

log(`Reviewing diff \`${DIFF}\` across ${DIMENSIONS.length} dimensions`)

// pipeline: each dimension reviews, then each of its findings is adversarially verified
// as soon as that dimension's review lands (no barrier between dimensions).
const results = await pipeline(
  DIMENSIONS,
  (d) => agent(
    `You are reviewing ONLY the changes in the current branch: run \`${DIFF}\` (if that base ref does not exist, use \`git diff origin/HEAD...HEAD\`) and read the changed hunks, plus the surrounding file when needed for context. Read CLAUDE.md and .claude/rules/ for this project's rules. Review through the ${d.key} lens. Focus on: ${d.focus}. Report ONLY real defects introduced or exposed by this diff, each with file and 1-indexed line. If the diff has none in this lens, return an empty findings array — do not invent issues.`,
    { label: `review:${d.key}`, phase: 'Review', agentType: d.agentType, schema: FINDINGS_SCHEMA }
  ),
  (review, d) => parallel(
    ((review && review.findings) || []).map((f) => () =>
      agent(
        `Adversarially verify this ${d.key} finding — actively try to REFUTE it by reading the code. Set refuted=true if it is not a genuine defect in the diff, is already guarded elsewhere, or you are uncertain. Only refuted=false when the failure scenario really holds.\n\nSummary: ${f.summary}\nLocation: ${f.file}:${f.line || '?'}\nScenario: ${f.failure_scenario}`,
        { label: `verify:${f.file}`, phase: 'Verify', agentType: 'code-reviewer', schema: VERDICT_SCHEMA }
      ).then((v) => ({ ...f, dimension: d.key, verdict: v }))
    )
  )
)

const confirmed = results
  .flat()
  .filter(Boolean)
  .filter((f) => f.verdict && f.verdict.refuted === false)

const severityRank = { high: 0, medium: 1, low: 2 }
confirmed.sort((a, b) => (severityRank[a.severity] ?? 3) - (severityRank[b.severity] ?? 3))

log(`Confirmed ${confirmed.length} finding(s) after adversarial verification`)
return { base: BASE, confirmed }
