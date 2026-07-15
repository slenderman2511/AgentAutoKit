# Apple Pay & Google Pay

**Apple Pay and Google Pay are not payment processors — they are wallets that return an encrypted card token you hand to a real PSP** (Stripe, Braintree, Adyen…). Do NOT build a standalone Apple/Google integration that settles money by itself; process the wallet token through your existing PSP.

## The one decision that matters

**Enable them as payment methods on Stripe (or your PSP), don't hand-roll them.** With Stripe's **Payment Element** or **Payment Request Button**, Apple Pay and Google Pay appear automatically on eligible devices, and the token is captured, decrypted, and charged by Stripe — you inherit its SCA, webhooks, refunds, and PCI scope. This is dramatically less code and risk than the raw Apple Pay JS / Google Pay API.

```js
// Stripe Payment Element already renders Apple/Google Pay when the device supports it —
// no separate wallet code, and fulfillment still happens on the Stripe webhook.
```

Only drop to the raw wallet APIs if you're not using a PSP that supports them (rare) — and then you still need a processor to charge the decrypted token.

## Apple Pay — prerequisites (even via a PSP)

- **Apple Developer merchant ID** and a payment-processing certificate (Stripe/your PSP guides this or manages it).
- **Domain verification:** host Apple's domain-association file at `/.well-known/apple-developer-merchantid-domain-association` on every domain that shows the button. With Stripe you register domains in the dashboard/API.
- **HTTPS + supported context:** Apple Pay on the Web only works in Safari / on Apple devices, over HTTPS. The button must be gated on `ApplePaySession.canMakePayments()` (or the Element's automatic detection).
- Merchant validation (the server-side session handshake) is handled for you by the PSP when you use its button/Element.

## Google Pay — prerequisites (even via a PSP)

- **Google Pay Business Console** merchant ID (required for `PRODUCTION`); `TEST` environment needs none.
- **Tokenization spec** points at your PSP: the `PaymentDataRequest` declares `tokenizationSpecification` with `gateway: 'stripe'` (or your PSP) and your gateway merchant id — the token is minted *for that PSP* to decrypt.
- Gate the button on `isReadyToPay()` before showing it; render the official Google Pay button per brand guidelines.
- Start in `environment: 'TEST'` (returns test tokens), switch to `'PRODUCTION'` only after PSP + Console setup.

## Same invariants still apply

Wallets change *how the card is entered*, not the rest of the flow:

- **Server still owns the amount** — the wallet sheet shows a total you computed server-side; re-verify on the webhook.
- **Fulfill on the PSP webhook**, not on the wallet's `onpaymentauthorized` client callback. The client callback can be spoofed; the Stripe/PSP webhook is the truth.
- **Idempotency, minor units (VND zero-decimal), secrets server-side** — all as in [principles.md](./principles.md).
- The wallet token is single-use and opaque — don't store or log it beyond charging it once.

## Testing

- **Google Pay:** `environment: 'TEST'` yields test tokens chargeable in Stripe test mode; no real card moves.
- **Apple Pay:** requires a real Apple device + a sandbox tester account (Apple's sandbox) or a live card in Stripe test mode; it can't be driven from a plain headless browser. In automated E2E, mock the wallet or test the underlying card path instead.

## Red flags to fix

- A bespoke Apple/Google Pay integration that tries to "process" payment without a PSP behind it.
- Fulfilling from the wallet's client-side authorization callback instead of the PSP webhook.
- Missing Apple domain-association file, or a Google `PaymentDataRequest` with no/wrong `tokenizationSpecification` gateway.
- Showing the button without `canMakePayments()` / `isReadyToPay()` gating.
- Google Pay left in `TEST` in production (or `PRODUCTION` without a Console merchant id).
- Assuming the wallet reduces work on amount validation, webhooks, or minor units — it doesn't.
