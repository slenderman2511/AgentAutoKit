---
name: payment-integration
description: Apply payment best practices when integrating, reviewing, correcting, or hardening online payment flows across gateways — Stripe, Apple Pay, Google Pay, 9Pay, and SePay. Use when asked to "add online payments", "integrate Stripe/9Pay/SePay", "accept Apple Pay / Google Pay", "verify a payment webhook", "generate a VietQR for bank transfer", "reconcile payments", "handle refunds/disputes", or when reviewing any checkout / PaymentIntent / webhook / IPN / signature-verification code. For running the repo's Stripe test-mode Playwright checkout flow, defer to e2e-flow.
user-invocable: false
---

# Payment Integration

Reference discipline for **integrating and hardening** online payments across five gateways of two very different kinds:

| Gateway | Kind | Money flow | Read |
|---|---|---|---|
| **Stripe** | Card/wallet PSP (international) | Charges card → you | [stripe.md](./stripe.md) |
| **Apple Pay** | Wallet (runs *through* a PSP) | Tokenized card → PSP → you | [wallets.md](./wallets.md) |
| **Google Pay** | Wallet (runs *through* a PSP) | Tokenized card → PSP → you | [wallets.md](./wallets.md) |
| **9Pay** | Vietnamese redirect gateway (e-wallet / ATM / credit / QR) | Hosted checkout → you | [9pay.md](./9pay.md) |
| **SePay** | Vietnamese bank-transfer / VietQR reconciliation | Bank → bank, SePay *notifies* | [sepay.md](./sepay.md) |

The mechanics differ, but the correctness bar is the same for all of them. Learn the invariants in [principles.md](./principles.md) first — most payment bugs and security holes are violations of those, not gateway-specific quirks.

## Golden rules (never violate — every gateway)

1. **The server owns the amount.** Never trust an amount, currency, or price sent from the client. Recompute the order total server-side and charge that. A client-set price is a free-money bug.
2. **The webhook/IPN is the source of truth for "paid" — not the browser redirect.** Users close tabs, redirects get spoofed or replayed. Fulfill the order (grant access, ship, mark paid) only after a **verified** asynchronous callback. Read [principles.md](./principles.md).
3. **Verify every webhook signature before trusting its body.** Stripe → `Stripe-Signature` HMAC; 9Pay → checksum/HMAC; SePay → `Apikey`/HMAC. An unsigned or unverified callback is an anonymous internet request that can mint paid orders.
4. **Idempotency everywhere.** Callbacks are delivered at-least-once (retries, replays). Key fulfillment by the gateway's transaction id and make re-delivery a no-op. Use idempotency keys on outbound charge creation.
5. **Never handle raw card data.** Use the gateway's hosted fields / SDK (Stripe Elements/Checkout, wallet sheets, 9Pay hosted page). Raw PAN in your code/logs = PCI scope you don't want. Read [principles.md](./principles.md).
6. **Secrets are server-only.** Secret/API keys, webhook secrets, and checksum keys live in server env/secret manager — never in client bundles, never committed. Publishable/public keys are the only client-side keys.
7. **Money is integer minor units — know each currency's exponent.** USD/EUR are 2-decimal (cents); **VND is zero-decimal** (whole đồng). Multiplying VND by 100 overcharges 100×. Read [principles.md](./principles.md).
8. **Test/sandbox first, never auto-deploy live keys.** Build against test mode / sandbox, verify the full pending→paid→refund lifecycle, then switch to live keys with explicit human confirmation.

## Reference files

### Cross-gateway fundamentals (read first)
[principles.md](./principles.md) — server-authoritative pricing, webhook-as-truth, signature verification, idempotency, PCI scope, minor units & currency, the order state machine (pending→paid→failed→refunded), reconciliation, refunds/disputes, secrets, audit logging, and testing.

### Stripe
[stripe.md](./stripe.md) — Checkout vs Payment Element vs raw PaymentIntents, `Stripe-Signature` webhook verification, idempotency keys, SCA/3DS, fulfilling on `checkout.session.completed`/`payment_intent.succeeded` (not the redirect), refunds, zero-decimal VND handling, and test cards.

### Apple Pay & Google Pay
[wallets.md](./wallets.md) — why you process wallets *through* a PSP (don't build a standalone integration), Apple merchant ID + domain verification, Google Pay tokenization spec + merchant ID, the Payment Request Button / Payment Element shortcut via Stripe, and test environments.

### 9Pay
[9pay.md](./9pay.md) — merchant credentials, the HMAC-SHA256 request signature, hosted redirect checkout, `return_url` vs IPN webhook, checksum verification of results, VND amounts, supported methods, and sandbox.

### SePay
[sepay.md](./sepay.md) — the VietQR / bank-transfer reconciliation model, embedding an order code in the transfer content, webhook payload fields, `Apikey`/HMAC auth, the required `200 {success:true}` response, Fibonacci retries & idempotency, amount verification, the no-refund-API reality, and the test environment.

### Running a correction/audit pass
[review-checklist.md](./review-checklist.md) — audit → fix → verify protocol: which files to open, the red-flag list, and the sandbox-first go-live gate.

## Correction workflow (short form)

1. **Locate the artifacts**: checkout/create-payment code, webhook/IPN handlers, signature-verification helpers, and where keys are read from. Grep for `PaymentIntent`, `checkout.session`, `Stripe-Signature`, `constructEvent`, `whsec_`, `Apikey`, `HMAC`, `VietQR`, `checksum`, `return_url`, `ipn`.
2. **Audit** against [review-checklist.md](./review-checklist.md) — record findings with file:line.
3. **Fix** highest-severity first: client-trusted amounts / unverified webhooks > missing idempotency > fulfillment-on-redirect > minor-unit/currency bugs > logging/secret hygiene.
4. **Verify** the full lifecycle in sandbox/test mode (pending → paid → refund, plus a replayed webhook proving idempotency).
5. **Propose go-live** as a diff + blast-radius summary; switch to live keys only after explicit human confirmation.
