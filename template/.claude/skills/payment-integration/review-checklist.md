# Correction pass: audit → fix → verify

Use this when asked to "add / audit / harden / fix" a payment integration. Work top-down by severity; verify the full lifecycle in sandbox; never flip to live keys unprompted.

## 1. Locate the artifacts

Grep the repo for:
- Checkout / create-payment: `PaymentIntent`, `checkout.session`, `create_payment`, `VietQR`, `qr`, `return_url`, `invoice_no`.
- Webhook / IPN handlers: `Stripe-Signature`, `constructEvent`, `whsec_`, `ipn`, `webhook`, `Apikey`, `HMAC`, `checksum`.
- Money & keys: `amount`, `currency`, `* 100`, `sk_`, `pk_`, secret/checksum key reads, `.env` usage.

## 2. Audit — red-flag checklist

**Cross-gateway** ([principles.md](./principles.md))
- [ ] Amount/currency computed **server-side**; never taken from the client.
- [ ] Order marked `paid` / fulfilled **only** from a verified webhook/IPN — never from the browser redirect.
- [ ] Every callback's **signature/auth is verified** before the body is trusted (raw-body for Stripe).
- [ ] Handlers are **idempotent** by the gateway's transaction/event id; outbound charges use idempotency keys.
- [ ] **No raw card data** touched/logged; hosted fields/SDK used. Full webhook bodies with PANs not logged.
- [ ] **Minor units** correct per currency — **VND is zero-decimal** (no ×100); no floats for money.
- [ ] Explicit order **state machine**; abandoned/expired handled; over/underpayments flagged.
- [ ] Secrets **server-only**, not committed; test vs live keys separated.
- [ ] Reconciliation fallback exists for missed webhooks; audit log of events.

**Stripe** ([stripe.md](./stripe.md))
- [ ] `constructEvent` over the **raw** body with `whsec_`; fast 2xx; idempotent by `event.id`.
- [ ] Fulfill on `payment_intent.succeeded` / `checkout.session.completed`, amount+currency re-checked.
- [ ] SCA/3DS not suppressed; `requires_action` handled; refunds/disputes via webhook.

**Wallets — Apple/Google Pay** ([wallets.md](./wallets.md))
- [ ] Processed **through a PSP** (Stripe), not a standalone integration; fulfill on the PSP webhook.
- [ ] Apple domain-association file present; Google `tokenizationSpecification` gateway + merchant id correct.
- [ ] Button gated on `canMakePayments()`/`isReadyToPay()`; Google not left in `TEST` in prod.

**9Pay** ([9pay.md](./9pay.md))
- [ ] Outbound request HMAC-SHA256 signed with fresh timestamp; secret key server-only.
- [ ] Result **checksum verified** with the checksum key (correct field order); IPN is source of truth, not `return_url`.
- [ ] Amount re-checked; IPN idempotent; VND not ×100.

**SePay** ([sepay.md](./sepay.md))
- [ ] Webhook authenticated (`Authorization: Apikey` / HMAC); only `transferType == 'in'` acted on.
- [ ] Order matched by payment `code`/content; `transferAmount == order amount` verified.
- [ ] Returns `200 {success:true}`; idempotent by transaction `id` (Fibonacci retries); unmatched/underpaid held for review.
- [ ] No assumption of a refund/capture API (manual bank refund, recorded).

## 3. Fix — order of operations

1. **Money-loss / security holes**: client-trusted amounts, unverified webhooks, fulfillment-on-redirect. Highest severity.
2. **Double-processing**: missing idempotency (duplicate deliveries / retries).
3. **Correctness**: minor-unit/currency bugs, amount not re-checked, wrong state transitions.
4. **Hygiene**: secret handling, logging PANs/PII, missing reconciliation, missing audit log.

Keep the smallest correct change; keep checkout + webhook + order-model changes together so they stay consistent.

## 4. Verify — full lifecycle in sandbox

- Drive **pending → paid → refund** in test mode with the gateway's test cards / simulated transactions.
- Prove the deny paths: **tampered amount** rejected, **invalid signature/Apikey** rejected, **replayed webhook** is a no-op, **underpayment** held.
- Use the gateway's simulator: Stripe CLI (`stripe listen` / `stripe trigger`), SePay `my.dev.sepay.vn` simulated transactions, 9Pay sandbox, Google Pay `TEST` env.
- An untested deny path is an unfinished fix.

## 5. Go-live gate — never auto-switch to live keys

- Show the diff and blast radius (which flows, which gateways, what could double-charge or under-collect).
- Confirm live vs test keys, production IPN/webhook URLs registered, domains verified (Apple Pay).
- Switch to live keys only after sandbox verification **and explicit human confirmation**. If the repo blocks deploys or has a project-specific payment/deploy skill, follow that instead.
