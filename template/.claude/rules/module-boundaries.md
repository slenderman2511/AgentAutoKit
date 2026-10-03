# Module & Package Boundaries — MUST FOLLOW

Goal: every piece of logic has ONE home, dependencies point ONE way, nothing is written twice.
Checked at design time by `arch-advisor` (plan review) and at PR time by `code-reviewer`.

> Fill in the project-specific layers and package graph below when installing the kit.

## 1. Dependency direction (no cycles)

```
routes / pages / UI            (e.g. src/app, src/components)
        ↓
app services / adapters        (e.g. src/lib/<domain> — DB, auth, env, framework)
        ↓
pure packages / domain core    (e.g. packages/* — no framework, no I/O)
```

- **Down only.** Lower layers never import upper layers. Pure packages never import the framework,
  the DB SDK or app code — enforce with a lint rule (`no-restricted-imports`) where possible.
- **Package graph = declared dependencies.** A new cross-package import must be declared in that
  package's manifest and must not create a cycle. Needed in both directions? Move it one level lower.
- **No cycles between domain folders either** — extract the shared piece downward.
- Existing violations: grandfather them by count, never add a new one.

## 2. Where new code goes

| Code is… | Home |
|---|---|
| Pure logic, no I/O, reusable | a package / pure module |
| Needs DB / auth / env | the app service layer for its domain |
| Route handler | thin: auth → scope check → call service → respond. No business logic inline. |
| UI | components; no DB access or business rules inside |

Create a new package only when the logic is pure, has ≥2 consumers (or another app needs it), and is
testable without infrastructure. Otherwise a module in the service layer is enough (YAGNI).

## 3. No overlap / duplication

- **Search before writing** a helper, type, constant or label map — reuse the existing one.
- **One owner per concept:** import the type a package exports instead of re-declaring it; extend a
  function with a parameter instead of copying it "with a small tweak".
- No `utils.ts` dumping grounds; no barrel re-exports that let upper layers leak downward.
- Removing duplication is in scope only when your change touches it; otherwise file a cleanup task.

## Review checklist
- [ ] Imports only point down; no new cycle.
- [ ] New cross-package import declared and respects the package graph.
- [ ] New logic lives in the home from §2; route handlers stay thin.
- [ ] No re-implemented helper/type/label map that already exists.
