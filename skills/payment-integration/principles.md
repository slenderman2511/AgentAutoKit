# Payment fundamentals (all gateways)

Most payment bugs and breaches are violations of these invariants, not gateway-specific quirks. Get these right and any gateway integration is 80% correct.

## The server owns the amount

The client tells you *what* to buy (cart, order id), never *how much*. Recompute the total on the server from trusted data (product prices, quantities, coupons you validate) and charge exactly that.

```
❌ createCharge({ amount: req.body.amount })          // client sets price → free-money bug
✅ const amount = priceOrder(await loadOrder(orderId)) // server computes from trusted data
   createCharge({ amount, orderId })
```

When the callback arrives, **re-check the paid amount and currency against the order**. If a customer paid less (tampered redirect, wrong QR amount, partial transfer), do not fulfill.

## The webhook/IPN is the source of truth — not the redirect

The browser return/redirect (`return_url`, `?success=true`, thank-you page) is a **UX signal only**. It can be closed, replayed, or forged. Grant entitlements / ship / mark-paid **only** from a verified server-to-server callback.

- Redirect → show "processing / thank you", optionally poll your own order status.
- Verified webhook → the single place you flip the order to `paid` and fulfill.
- Never fulfill in the redirect handler. Never assume "no webhook yet" means "not paid" — reconcile (below).

## Verify the callback signature before trusting the body

Every gateway signs its callbacks; an unverified endpoint is an anonymous POST that anyone can use to mint paid orders.

- **Stripe:** verify `Stripe-Signature` with the endpoint's `whsec_...` secret using the SDK (`constructEvent`) over the **raw** request body. Parsing JSON before verifying breaks the signature.
- **9Pay:** verify the result checksum / HMAC with your checksum key before acting on `return_url` or IPN data.
- **SePay:** authenticate the webhook via the configured method (`Authorization: Apikey ...`, or HMAC-SHA256) before accepting the transaction.

Reject (4xx) anything that fails verification; log the attempt. Verify on the **raw bytes** — many frameworks' JSON body parsers mutate the payload and invalidate the signature, so exempt webhook routes from body parsing or capture the raw body.

## Idempotency — callbacks arrive more than once

Gateways deliver at-least-once and retry on timeout/failure (SePay backs off on a Fibonacci schedule; Stripe retries for days). The same event WILL hit your endpoint twice.

- Key fulfillment by the gateway's unique id (`event.id`, transaction id, `referenceCode`). Store processed ids; a duplicate is a no-op that still returns success.
- Wrap "mark paid + fulfill" in a transaction / conditional update so concurrent deliveries can't double-fulfill.
- On **outbound** charge creation, send an **idempotency key** (Stripe supports this natively) so a retried create doesn't double-charge.

## Never touch raw card data (PCI)

Let the gateway collect card details in its own hosted UI / SDK so the PAN never reaches your servers — this keeps you in the smallest PCI scope (SAQ A).

- Stripe → Checkout (hosted) or Elements/Payment Element (iframe fields). Apple/Google Pay → the wallet sheet. 9Pay → its hosted redirect page.
- **Never** log full card numbers, CVV, or full webhook bodies containing PANs. Never store CVV. Mask everything.
- The only card-ish token you keep is the gateway's (`pm_...`, wallet token) — opaque and safe.

## Money is integer minor units — mind the exponent

Represent money as integers in the currency's smallest unit. The exponent varies:

| Currency | Decimal places | 100 units = |
|---|---|---|
| USD, EUR | 2 | $1.00 → `100` |
| **VND** | **0** | 1.000 ₫ → `1000` (NOT `100000`) |

- VND is a **zero-decimal** currency. Passing `amount * 100` overcharges by 100×. Stripe treats VND as zero-decimal; 9Pay and SePay use whole đồng.
- Never use floats for money (`0.1 + 0.2`). Compute in integer minor units; format for display only.
- Always pair an amount with its currency and validate both on the callback.

## The order state machine

Model payment as explicit states, transitioned only by trusted signals:

```
created → pending (awaiting payment)
        → paid       (verified webhook, amount+currency match)   → fulfill
        → failed / cancelled / expired
paid    → refunded / partially_refunded  (verified refund event)
        → disputed / charged_back        (Stripe dispute webhook)
```

- Fulfillment is a side effect of entering `paid`, done once (idempotent).
- Keep the gateway's ids on the order (payment intent / transaction / reference) for reconciliation and support.
- Handle `expired`/`cancelled` so abandoned checkouts don't linger as `pending` forever.

## Reconciliation — don't rely on webhooks alone

Webhooks can be missed (endpoint down, deploy, network). Have a fallback:

- A scheduled job that queries the gateway (or your bank/SePay dashboard) for recent transactions and reconciles any `pending` order past a threshold.
- For SePay specifically, the incoming bank transfer is the truth; match by the order code embedded in the transfer content, and alert on unmatched transfers.
- Detect and flag **over/underpayments** and **duplicate payments** for manual review rather than silently accepting.

## Refunds & disputes

- Refund through the gateway's API where one exists (Stripe `refunds.create`; 9Pay refund API). Record the refund event and move the order to `refunded`.
- **SePay has no refund API** — refunds are manual bank transfers; record them against the order and reconcile.
- Handle Stripe **disputes/chargebacks** via webhook (`charge.dispute.created`) — respond with evidence within the window; treat funds as at-risk.
- Never refund from an unauthenticated endpoint or on a client request without server-side authorization.

## Secrets & keys

- Secret/API keys, webhook secrets (`whsec_`), and checksum keys are **server-only** — env vars / secret manager, never committed, never in client bundles.
- Only publishable/public keys (`pk_...`, Google Pay merchant id for the client) belong client-side.
- Separate test and live keys; make it obvious which environment you're in; never point test UI at live keys or vice-versa.
- Rotate on suspected leak; scope keys minimally where the gateway supports restricted keys.

## Audit logging

- Log every state transition and gateway event id (not card data) to an append-only audit trail — essential for support, disputes, and reconciliation.
- Log verification failures and unmatched callbacks; alert on spikes.

## Testing

- Build against **test mode / sandbox** with the gateway's test cards / simulated transactions.
- Test the deny paths, not just the happy path: tampered amount, invalid signature, **replayed webhook** (must be a no-op), underpayment, expired session.
- Use the gateway's webhook simulator / CLI (e.g. `stripe listen` / `stripe trigger`, SePay's `my.dev.sepay.vn` simulated transactions) to exercise callbacks locally.
