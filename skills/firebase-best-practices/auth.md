# Firebase Auth hardening

Auth is the identity source that security rules trust. If Auth is weak, rules built on `request.auth` inherit the weakness.

## App Check — stop abuse from unauthorized clients

App Check attests that requests come from your genuine app (via reCAPTCHA/Enterprise on web, DeviceCheck/App Attest on iOS, Play Integrity on Android), blocking scripted abuse of Firestore, Storage, Functions, and Auth.

- Enable App Check for every backend a client can hit. Run in **monitoring mode** first to measure legitimate traffic, then **enforce**.
- It complements security rules (which handle *authorization*); App Check handles *is this a real client*. You want both.

## Email-enumeration protection

Modern Firebase Auth returns generic errors so attackers can't probe which emails are registered. Keep **email enumeration protection enabled** and don't reintroduce leaks by branching UI on `auth/user-not-found` vs `auth/wrong-password` — show one generic "invalid credentials" message.

## Password policy & bot defense

- Configure a **password policy** (min length, required character classes) in the Auth settings.
- Keep **reCAPTCHA / SMS abuse protection** on for phone auth and password sign-in to blunt credential-stuffing and toll-fraud.
- Prefer federated providers (Google/Apple/OIDC) or email-link over passwords where you can.

## Multi-factor authentication

Offer MFA (TOTP and/or SMS) for privileged accounts at minimum — anyone with `admin`/`owner` roles. Enforce it for those roles rather than leaving it optional.

## Sessions, tokens, and revocation

- **ID tokens expire in ~1 hour**; the SDK auto-refreshes using the refresh token. Custom-claim changes only take effect on refresh — see the propagation note in [rbac-roles.md](./rbac-roles.md).
- To **revoke a user immediately** (compromised account, role downgrade that must be instant): `getAuth().revokeRefreshTokens(uid)`, then verify tokens server-side with `verifyIdToken(token, /* checkRevoked */ true)`. Rules can also compare `request.auth.token.auth_time` against a stored revocation time.
- For web, tune session persistence deliberately (`local` vs `session` vs `none`) to the app's risk profile. For SSR/session-cookie flows, use `createSessionCookie` with a bounded lifetime rather than shipping ID tokens around.

## Admin SDK safety (server only)

The Admin SDK **bypasses all security rules** — it is fully privileged.

- Never bundle a service-account key or Admin SDK into client/web/mobile code. Keep keys in server env/secret manager; never commit them.
- Run Admin SDK only in trusted server contexts (Cloud Functions, backend routes). On Google infrastructure prefer Application Default Credentials over downloaded key files.
- Because it bypasses rules, server code must do its **own** authorization — re-check the caller's identity and role before privileged writes. Don't assume "it's server-side so it's safe."
- Verify inbound ID tokens with `verifyIdToken` on every privileged endpoint; don't trust a `uid` sent in the request body.

## Red flags to fix

- Service-account JSON committed to the repo or referenced from client bundles.
- Sign-in error handling that distinguishes "no such user" from "wrong password" (enumeration leak).
- Elevated roles without enforced MFA.
- No App Check on a public-facing Firebase backend.
- Server routes that trust a client-supplied `uid`/`role` instead of verifying the ID token.
- No revocation path for compromised accounts (relying solely on 1-hour token expiry).
