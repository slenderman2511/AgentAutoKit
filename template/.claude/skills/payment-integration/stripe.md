# Stripe

Stripe is the international card/wallet PSP and the recommended way to also accept Apple Pay & Google Pay (see [wallets.md](./wallets.md)). Apply the cross-cutting invariants in [principles.md](./principles.md); this file is Stripe specifics.

## Pick the integration surface

| Surface | Use for | PCI / effort |
|---|---|---|
| **Checkout** (Stripe-hosted page) | Fastest path; Stripe hosts the whole payment page, handles cards + wallets + SCA | Lowest (SAQ A), least code |
| **Payment Element** (embedded) | Custom UI, still Stripe-hosted iframe fields; one component covers cards, Apple/Google Pay, local methods | Low (SAQ A) |
| **Raw PaymentIntents + manual confirm** | Full control / server-driven flows | More code, more edge cases |

Default to **Checkout** or **Payment Element** — they handle SCA/3DS, wallets, and localization for you and keep you in the smallest PCI scope. Reach for raw PaymentIntents only when you need server-side confirmation control.

## The core flow (PaymentIntent)

1. **Server** creates a PaymentIntent (or Checkout Session) with a **server-computed** amount + currency, an idempotency key, and metadata linking it to your order:
   ```js
   const pi = await stripe.paymentIntents.create(
     { amount, currency: 'usd', metadata: { orderId } },
     { idempotencyKey: `pi_${orderId}` }
   );
   ```
2. **Client** confirms with the `client_secret` via Elements/Checkout — card data goes straight to Stripe, never your server.
3. **Stripe** runs SCA/3DS if required (the Element handles the challenge UI).
4. **Webhook** tells you the truth: fulfill on `payment_intent.succeeded` (or `checkout.session.completed`), NOT on the browser redirect.

## Verify webhooks correctly

This is the #1 Stripe bug. Verify the `Stripe-Signature` header against the endpoint's `whsec_...` secret using the **raw** request body:

```js
// Route MUST receive the raw body (e.g. express.raw), not parsed JSON.
const event = stripe.webhooks.constructEvent(rawBody, req.headers['stripe-signature'], endpointSecret);
```

- If your framework parses JSON before the handler, the signature check fails — exempt the webhook route from body parsing / capture the raw bytes.
- `constructEvent` also rejects stale timestamps (replay protection). Don't roll your own HMAC.
- Return `2xx` **fast** (within seconds) — do heavy work async or after acking, or Stripe retries and you get duplicate deliveries.
- Idempotently handle each `event.id`; Stripe retries for up to ~3 days on non-2xx.

## Fulfill on the webhook, reconcile the redirect

- The success `return_url` / `?redirect_status=succeeded` is UX only. Show "thank you / processing"; flip the order to `paid` from the verified webhook.
- Guard fulfillment: match `paymentIntent.amount`/`currency` and `metadata.orderId` to the order before granting anything.
- For Checkout, listen to `checkout.session.completed`; for async payment methods also handle `checkout.session.async_payment_succeeded/failed`.

## SCA / 3D Secure

- SCA is mandatory for many regions (EEA). The Payment Element / Checkout handles the 3DS challenge automatically — don't suppress it.
- With raw PaymentIntents, handle the `requires_action` status and let `stripe.handleNextAction`/`confirmCardPayment` drive the challenge; don't treat `requires_action` as failure.

## Refunds & disputes

```js
await stripe.refunds.create({ payment_intent: pi.id, amount });  // omit amount for full
```
- Move the order to `refunded`/`partially_refunded` from the `charge.refunded` webhook, not optimistically.
- Handle disputes via `charge.dispute.created` — submit evidence within the window; funds are withheld until resolved.

## Money & currency

- Integer minor units. **VND is zero-decimal** — pass `10000` for 10.000 ₫, never `10000 * 100`. USD/EUR are cents. Confirm each currency's exponent rather than assuming ×100.
- Always create the intent with an explicit `currency`; validate it on the webhook.

## Keys, testing, and the CLI

- `sk_...` (secret) and `whsec_...` (webhook secret) are **server-only**; `pk_...` (publishable) is the only client key.
- Develop with **test mode** keys and test cards: `4242 4242 4242 4242` (success), `4000 0025 0000 3155` (3DS required), `4000 0000 0000 9995` (declined).
- Use the Stripe CLI to test webhooks locally: `stripe listen --forward-to localhost:3000/webhook` and `stripe trigger payment_intent.succeeded`.
- This repo's Playwright flow drives real Stripe **test-mode** Checkout (`checkout.stripe.com`, card `4242...`) — see the `e2e-flow` skill for running it.

## Red flags to fix

- Fulfilling the order in the redirect/return handler instead of on a verified webhook.
- `constructEvent` fed parsed JSON instead of the raw body (or a hand-rolled HMAC / no verification at all).
- Amount taken from the client, or webhook amount/currency not re-checked against the order.
- No idempotency key on create; webhook handler not idempotent by `event.id`.
- `sk_`/`whsec_` in client code or committed; test and live keys mixed.
- `VND` amounts multiplied by 100; floats used for money.
- Suppressing/avoiding 3DS, or treating `requires_action` as an error.
