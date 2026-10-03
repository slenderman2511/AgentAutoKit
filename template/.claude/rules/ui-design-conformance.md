# UI Design Conformance — built UI vs design/prototype — MUST FOLLOW

A UI feature that compiles and passes review still routinely ships **not matching its prototype /
design** (layout, hierarchy, states, spacing, copy drift). Type-checks, `code-reviewer` and `ui-verify`
check rules, not "does it look like what we agreed". This loop closes the gap.

## When it fires

After implementation, BEFORE the review gate, whenever the diff adds or visibly changes a page/screen
or a user-facing component AND a reference exists: a `ui-prototype` file (or the prototype URL linked
in the issue / plan header), a design-tool screen (Figma, Stitch…), or — with no prototype — the
project's design-system doc (`DESIGN.md` / design rules in `.claude/rules/`) as the reference.
Skip for: copy/i18n-only diffs, internal tweaks with no visual change, pure logic/API diffs.

## The loop (max 2 rounds)

1. **Capture the built UI** — dev server + Playwright at **375 px and 1280 px** (the `ui-verify`
   live-pass setup). Screenshot every state the prototype shows (default · empty · loading · error ·
   success · key interaction). Screenshot the prototype at the same widths.
2. **Audit — `hallmark audit`** (read-only, ranked punch list) on the built screens, WITH the
   prototype screenshots as the reference. Three buckets, each item =
   `screen/state · what differs · proposed change · file:line`:
   - **A. Drift from prototype/design** — layout, hierarchy, spacing, missing/extra elements, states, copy.
   - **B. Design-system violations** — the project's design rules, responsive rules, tap-target/a11y basics.
   - **C. Hallmark slop findings** — generic/AI-looking patterns.
3. **Triage — `code-reviewer` in UI-conformance triage mode** (read-only), per proposal:
   - **ACCEPT** — restores the prototype, fixes a design-system/responsive/a11y violation, or is a
     clear quality win inside the feature's own files.
   - **REJECT** — contradicts project rules (hallmark's themes, fonts or "structural variety" NEVER
     override the project's design tokens/theming), redesigns beyond the prototype, touches files
     outside the feature, or is taste-only with no prototype/rule backing.
   - **ASK PO** — prototype and design system disagree, or the prototype itself looks wrong → list
     it for the user, don't decide.
4. **Apply** — `implementer` applies ACCEPTED items only, same branch/PR (one task = one PR).
   Re-run step 1 for the changed screens (+ `ui-verify` contrast pass if colours moved).
5. **Record** — PR body gets a **UI conformance** section: prototype link, before/after screenshots
   (375 + 1280), the ACCEPT/REJECT/ASK table with one-line reasons. ASK items go to the user before merge.

Round 2 only re-audits what round 1 changed. After 2 rounds, remaining drift is listed in the PR and
decided by the user — no third loop.

## Guardrails

- Hallmark runs in **`audit` only** here — never `redesign` / the default design flow on existing
  production UI.
- Project design rules outrank hallmark's opinions.
- Screenshots go in the PR / a scratch dir, never committed into the source tree.
