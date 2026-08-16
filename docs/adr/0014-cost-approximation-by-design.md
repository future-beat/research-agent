# ADR-0014 — Reported cost is an estimate by design, and invoice reconciliation is rejected

**Status:** Accepted
**Source:** Phase 22 (2026-08-16), `REQ-limitations-recorded`

## Context

Every cost figure this service reports is computed by the service, from its own tables, at
the moment the work happens. `usage.price_for()` resolves an effective-dated rate for a
date and `record()` prices a call by the model name it was actually dispatched to;
`/pricing` publishes the rate window and the multipliers in effect; `cost_usd` rides in the
`result` event of the SSE payload, in the same response as the answer. **Nothing in this
tree has ever read a bill**, and no code path exists that could.

That position has been operationally true since Phase 14 and stated in passing in three
places, but it has never been written down as a decision. This record writes it down —
which matters now because the README bullet that carried it is being rewritten to point at
a record, and a bullet pointing at nothing is what this milestone's close-out exists to
end.

**Provider token counts are telemetry, not billing truth, and that is measured rather than
assumed.** [`docs/OPERATIONS.md`](../OPERATIONS.md) carries the measurement with a date: on
2026-08-09 a 12-note corpus the local tokenizer counted at **40** tokens came back from
Voyage reported as **25**, and a single one-word document came back as **0** — which
nothing that returns an embedding can actually have cost. `usage.record_embedding`'s
docstring states the same epistemic position from the code's side: *"Zero tokens is not an
error. Voyage's reported count is telemetry, not billing truth,"* and that it records as
$0.00 through the normal priced path rather than raising. Two independent surfaces, one
conclusion: the number in the response is what the response said, not what the vendor will
charge.

**No multipliers are invented across vendors.** `COST_DISCOUNT_FACTOR` and the
`inference_geo` rate are Anthropic dimensions — a negotiated Anthropic discount and a
Claude data-residency surcharge. Voyage is a different vendor on a different rate card, and
applying either there would invent a discount nobody negotiated. The asymmetry is
deliberate and is the reason the two recording paths differ at all.

**The billing authority is, and stays, the provider dashboards.** Anthropic's Cost page and
Voyage's usage dashboard are the only surfaces that can answer what was billed. OPERATIONS
already says this of Voyage in those words. This record says it of both.

**What the estimate can be wrong about, stated rather than hand-waved.** A reported figure
can drift from an invoice through a reported token count that disagrees with the tokenizer
(measured, above); through a rate table that is correct but not yet updated for a price
change the vendor has made; through a multiplier an operator set that does not match a real
contract; through spend the service does not meter at all — embedding spend is absent from
`/metrics` entirely, and the eval judge's calls bill separately from the pipeline the
recorder meters. The list is finite and none of its entries is closed by reading a bill
once a day.

## Decision

**Reported cost is an estimate by design. It is computed client-side from effective-dated
rate tables, published against `/pricing` so its inputs are inspectable, and it is never
represented as the invoice. The service does not reconcile against billing data, and no
reconciliation job will be built for this milestone or the shape of service it is.**

The honest backstop for what was actually billed is the provider's own dashboard, named as
such wherever a cost figure is surfaced. The control that bounds financial exposure is not
the accuracy of the estimate — it is the global rolling daily spend cap, whose only input
is the `runs` ledger this service writes itself (`metrics.spend_since`), and which is
therefore exactly as reliable as the estimate feeding it and no more. That is a bound on
exposure, not a claim of precision, and the two should not be confused.

## Consequences

### Accepted

- **A reader treats `cost_usd` as an estimate, because every surface that shows it says
  so.** `/pricing` shows the rate window and the multipliers, which is where the number is
  read from rather than from prose in a document that goes stale.
- **The service can be wrong about the bill and still be correct about itself.** A
  divergence between `cost_usd` and an invoice line is a rate-table or telemetry gap to
  investigate, not a defect in the run that reported it. Framing it that way is only
  possible because this record refuses to claim the stronger thing.
- **The spend cap's guarantee is bounded by the same estimate.** A cap fed by an
  under-reported cost under-counts spending. This is the honest reading of ADR-0007's
  global cap and is stated here rather than left for a reader to derive: the cap bounds
  exposure *as this service measures it*, which is the only thing any client-side control
  can bound.
- **Embedding spend remains unmetered in `/metrics`,** and stays a known gap rather than
  being quietly folded into an estimate that would then be wrong in a new way.
- **This record supersedes nothing.** No prior record argues a cost position; DEC-12's
  unpriced-model fail-loud rule and ADR-0007's spend cap both stand untouched, and this
  record depends on the first rather than reopening it — an unpriced model must fail loud
  precisely *because* the estimate is the only number there is.

### Rejected alternatives

- **Invoice reconciliation against Anthropic's Usage & Cost Admin API.** The obvious
  candidate, and the one the roadmap named. It is designed for this: the endpoint's own
  documentation lists *"Cost reconciliation: Match internal records with Anthropic billing
  for finance and accounting teams"* as a use case, so it is rejected on **fit for this
  service**, not on capability. Four reasons, each a documented property of the API rather
  than an impression:

  1. **It needs an Admin API key, and for a Claude Console organization that key cannot be
     narrowed.** The endpoints require an Admin API key (`sk-ant-admin01-…`), which is a
     different and larger credential than the two this service manages. The docs state that
     Console keys *"do not have selectable scopes; every key carries full access to all
     endpoints that accept Admin API keys"* — today that set spans the Admin API, the
     Analytics APIs, the Compliance API, the Spend Limits API, the Rate Limits API, and
     this one. Wiring cost reconciliation would therefore introduce a credential that reads
     organization-wide across every workspace, into a service whose entire secret posture
     is two narrow, per-vendor API keys that never reach an image layer. **The blast radius
     of the fix exceeds the blast radius of the problem**, and the problem is a cost figure
     that already says it is an estimate. The same docs note the Admin API is unavailable
     to individual accounts at all, so for a single-developer project the precondition is
     an organization that does not exist yet.
  2. **It is a daily aggregate with no per-run dimension.** `/v1/organizations/cost_report`
     supports *"Daily granularity only (`1d`)"* and groups only by workspace or
     description. This service's cost claim is per-run — `cost_usd` is emitted per
     response, per session. The API can answer "what did this workspace cost yesterday"; it
     cannot answer "what did *this run* cost." Splitting a daily aggregate back across
     individual runs is a new estimation problem layered on the one being reconciled, which
     is not a reconciliation.
  3. **It lags the number it would be reconciling.** *"Usage and cost data typically
     appears within 5 minutes of API request completion, though delays may occasionally be
     longer."* This service reports cost synchronously, in the same response as the answer.
     A figure that arrives five-or-more minutes later cannot correct a figure that has
     already been sent, so the best it could do is amend a historical ledger — which is a
     different feature from the one the bullet promised.
  4. **It is real infrastructure for a demo-scale service.** A scheduled job, storage for
     the daily aggregate, correlation logic against the `runs` ledger, and a reconciliation
     surface someone reads. That is a subsystem, built to improve a number whose honest
     backstop — the vendor dashboard — is one click away and already documented.

  **Provenance, and one thing that changed.** These properties were read from Anthropic's
  official Usage & Cost API and Admin-API-key documentation on 2026-08-16 by this phase's
  research, and re-read from the same pages at execution before this record was written.
  Reasons 2 and 3 reproduced verbatim. Reason 1 did not: the research quoted *"Admin API
  keys are owned by the organization and remain active even after the creator is removed,"*
  and that sentence was **not present on any of the three pages at re-read**. The
  no-selectable-scopes sentence quoted above is what the documentation says today, and it
  is a stronger form of the same point, so reason 1 stands on the current text rather than
  on the earlier quote. Recorded this way deliberately: a rejection reason resting on a
  sentence that is no longer there would be a worse record than one that says which
  sentence moved.

- **Reconciling against Voyage instead, or as well.** Rejected for a simpler reason: the
  measured 40-vs-25-vs-0 disagreement above is between the tokenizer and the API's own
  reported count, and no billing endpoint is involved on either side of it. OPERATIONS
  already names the usage dashboard as the only authority, which is the same answer this
  record gives for Anthropic.

- **Dropping `cost_usd` from the response entirely.** Rejected. An estimate that states its
  own nature is more useful than silence, and the figure is load-bearing beyond display —
  the spend cap, the record-run quote, and the `--record` cost preview all read the same
  priced path. Removing the number would remove the controls with it.

- **Presenting the estimate as the invoice and quietly dropping the caveat.** Named here so
  the alternative is on the record as considered and refused. It is the only option that
  makes the README bullet disappear without the work, and it is the one thing this project
  has consistently declined to do — the same instinct that keeps `pricing_unknown` loud
  (DEC-12) and keeps a `0`-token embedding recorded at $0.00 rather than silently
  corrected.
