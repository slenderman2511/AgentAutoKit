# SePay

SePay is **not a card processor** — it's a Vietnamese **bank-transfer / VietQR reconciliation** service. Money moves bank-to-bank (customer → your linked bank account); SePay watches that account and **fires a webhook the moment a matching transfer arrives**. Your job is to match the incoming transfer to an order. Apply the invariants in [principles.md](./principles.md); this file is SePay specifics. Confirm exact fields against the current SePay docs (developer.sepay.vn) — vendor details change.

## The reconciliation model

1. You **link a bank account** to SePay (SePay reads its transaction feed).
2. For an order, you **generate a VietQR** encoding: your bank account + (optionally) the exact amount + a **payment code / reference in the transfer content** (e.g. `DH12345`). Show the QR (and account/amount/content for manual transfer).
3. **Customer transfers** via their banking app (scans the VietQR or types the details). The order stays `pending`.
4. **SePay detects** the incoming credit on your account and **POSTs a webhook** to your endpoint with the transaction details.
5. **You** authenticate the webhook, parse the payment code from the content, match it to the pending order, verify the **amount**, then mark `paid` and fulfill — **idempotently**.

The payment code in the transfer content is the join key. Make it unique per order and easy for SePay's matching to extract (SePay can be configured with a code prefix/pattern).

## Webhook payload (typical fields)

SePay POSTs JSON on every matching transaction — expect fields like:

| Field | Meaning |
|---|---|
| `id` | SePay transaction id — **use for idempotency** |
| `gateway` | Bank name (e.g. `Vietcombank`) |
| `transactionDate` | Timestamp of the bank transaction |
| `accountNumber` | Your receiving account |
| `subAccount` | Virtual/sub-account if used |
| `transferType` | `in` (credit) / `out` (debit) — only act on `in` |
| `transferAmount` | Amount in **VND (whole đồng)** |
| `accumulated` | Running balance |
| `code` | Payment code SePay parsed from the content (your order ref) |
| `content` | Full transfer description/memo |
| `referenceCode` | Bank's reference number |
| `description` | Raw bank description |

Match order by `code` (fallback: parse `content`). Confirm `transferType == 'in'` and `transferAmount == order amount` before fulfilling.

## Authenticating the webhook

SePay supports several methods — configure one and enforce it:

- **API Key** — SePay sends header `Authorization: Apikey YOUR_API_KEY`. Reject requests missing/mismatching it.
- **HMAC-SHA256** — verify the signature over the payload.
- (OAuth 2.0 / none also exist — never use "none" in production.)

Never trust the payload until the configured auth check passes.

## The required response & retries

- Reply **HTTP 200 with `{"success": true}`** promptly (within SePay's timeout, ~30s) so SePay marks the webhook delivered.
- On any non-success/timeout, **SePay retries** with intervals increasing on a **Fibonacci** schedule — so your handler MUST be **idempotent**: dedupe by transaction `id`; a re-delivery re-returns success without double-fulfilling.
- Do the matching/fulfillment inside a transaction or conditional update so concurrent retries can't double-process.

## Amounts & the no-refund reality

- **VND, whole đồng.** `transferAmount` is already in đồng — no ×100, no floats. Verify it equals the order total; flag under/overpayments for manual review.
- **SePay has no refund/charge API** — it only *observes* bank transfers. Refunds are **manual bank transfers** you perform and then record against the order. There's also no "capture" — the customer's transfer is final on arrival.
- Because there's no hosted checkout, there's no card data and no PCI card scope here — but treat bank/account data carefully and don't log full memos containing personal info needlessly.

## Reconciliation & edge cases

- **Missed webhook** (endpoint down): SePay retries, and you can also poll SePay's transactions API / dashboard for recent credits to reconcile stale `pending` orders.
- **Unmatched transfer** (no/garbled code, wrong amount): don't auto-fulfill — queue for manual review and alert.
- **Duplicate transfer** or **wrong order code**: detect and hold; never fulfill twice.

## Testing

- Use the SePay **test environment** (`my.dev.sepay.vn`) to create **simulated transactions/webhooks** and drive your handler end-to-end.
- Test: valid match → paid; replayed webhook → no-op; underpayment → held; missing/invalid `Apikey` → rejected.

## Red flags to fix

- Accepting the webhook without checking `Authorization: Apikey` / HMAC.
- No idempotency by transaction `id` → Fibonacci retries double-fulfill.
- Acting on `transferType == 'out'`, or not verifying `transferAmount == order amount`.
- Auto-fulfilling unmatched/underpaid transfers instead of holding for review.
- Not returning `200 {success:true}` (SePay keeps retrying forever).
- Treating SePay as if it can refund/capture — it can't; refunds are manual.
- Multiplying VND by 100 / using floats.
