# 9Pay

9Pay is a Vietnamese payment gateway offering hosted checkout across e-wallet, domestic ATM cards, credit cards, and QR. Integration is a **redirect (hosted-page) flow** with an HMAC-signed request and a checksum-verified result. Apply the invariants in [principles.md](./principles.md); this file is 9Pay specifics. Always confirm exact field names/URLs against the current 9Pay merchant docs — vendor details change.

## Credentials

Obtain from the 9Pay merchant portal, store **server-side only**:
- **Merchant key** (public identifier of your merchant account)
- **Secret key** — signs outbound requests (HMAC-SHA256)
- **Checksum key** — verifies inbound results (return_url + IPN)

## The redirect flow

1. **Server** builds a create-payment request with a **server-computed** amount (VND, whole đồng), your order id (`invoice_no`), description, `return_url`, and IPN/callback url.
2. **Server** signs the request (below) and redirects the customer to 9Pay's hosted payment page.
3. **Customer** picks a method (9Pay wallet / ATM / credit / QR) and pays on 9Pay's page — you never see card data.
4. **9Pay** redirects the browser back to `return_url` **and** sends a server-to-server **IPN** to your callback url.
5. **You** verify the checksum on the IPN, re-check amount + order, and only then mark the order `paid` and fulfill.

## Request signing (HMAC-SHA256)

9Pay authenticates API requests with a base64 HMAC-SHA256 over a canonical string:

```
signature = base64_encode(
  HMAC_SHA256(
    <HTTP method> + "\n" +
    <request URI> + "\n" +
    <timestamp>   + "\n" +
    <canonicalized request data>,
    <merchant_secret_key>
  )
)
```

- Build the canonical string exactly as 9Pay specifies (field order, encoding) — a mismatch means signature rejected.
- Include a fresh `timestamp`; stale timestamps are rejected (replay protection).
- Never expose the secret key or compute the signature client-side.

## Verifying the result (checksum)

Both the `return_url` payload and the IPN carry a **checksum**. Recompute it with your **checksum key** (SHA-256 over the returned fields) and compare before trusting anything:

```
expected = hash_sha256(<returned fields in 9Pay's specified order> + <checksum_key>)
if (expected !== received.checksum) reject();   // forged/tampered callback
```

- Treat the **IPN** as the source of truth, not the browser `return_url` (users close tabs; redirects can be replayed).
- After checksum passes: verify `status == success`, the paid **amount == order amount**, currency VND, and the `invoice_no` maps to a real pending order. Then fulfill **idempotently** (dedupe by 9Pay's transaction id).
- Respond to the IPN as 9Pay expects (HTTP 200 / documented ack) so it stops retrying.

## Money

- **VND is zero-decimal.** Amount is whole đồng — `10000` means 10.000 ₫. Never multiply by 100. No floats.

## Sandbox & go-live

- Integrate and test against 9Pay's **sandbox** credentials/endpoints first; run the full pending → paid → (refund if used) lifecycle and a replayed IPN.
- Switch to production merchant key / secret / checksum key only after sandbox verification and explicit human confirmation. Configure the production IPN url in the 9Pay portal.

## Red flags to fix

- Marking the order paid from `return_url` instead of the checksum-verified IPN.
- Skipping checksum verification, or verifying with the wrong key / field order.
- Amount taken from the client, or IPN amount not re-checked against the order.
- Secret/checksum key in client code or committed.
- VND amount multiplied by 100.
- IPN handler not idempotent (no dedupe by transaction id) → double fulfillment on retry.
- Stale/missing timestamp in signed requests.
