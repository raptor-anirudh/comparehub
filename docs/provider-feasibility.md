# Provider Feasibility

**Research date:** 2026-10-10. Method: web search of official documentation.
**Caveat:** I could only read documentation snippets, not log into any partner
dashboard. Eligibility is account-specific and MUST be confirmed by the account
owner before any real integration work starts. Nothing below has been exercised
against a live endpoint.

Legend: **Verified** = stated in official documentation I retrieved.
**Unverified** = from third-party sources or inferred; do not build on it.

## Summary

| Provider | Official programmatic access? | Status for CompareHub |
|---|---|---|
| Amazon (India) | Creators API (replaces PA-API 5) | Candidate. Blocked on account eligibility. |
| Flipkart | Flipkart Affiliate APIs | Candidate. Blocked on affiliate registration. |
| Uber (Moto) | No verified self-serve fare API | Blocked. Mock only. |
| Rapido | No official public API found | Blocked. Mock only. Do NOT use reverse-engineered endpoints. |

## Amazon

- **Verified:** PA-API 5 is deprecated. Amazon's own PA-API docs state it
  "will be deprecated on May 15th, 2026" and direct users to the Creators API.
  Calls to PA-API now return HTTP 403 `AccessDeniedException`, per Amazon's
  deprecation notice page.
- **Verified:** The Creators API is REST-based and documented under the Amazon
  Associates program
  (https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction).
- **Unverified (third-party blog):** OAuth 2.0 client-credentials auth, a single
  global endpoint, final-accepted Associates status, and a minimum of 10
  qualifying referred sales in 30 days. These come from a community post, not
  Amazon. Confirm in the Associates dashboard.
- **Unverified:** Whether Amazon India (amazon.in) Associates accounts have
  Creators API access, its rate limits, and whether price-comparison use is
  permitted under the Associates Program Operating Agreement.
- **Consequence:** Any older tutorial or library that signs PA-API v5 requests
  is obsolete. Do not implement it.

## Flipkart

- **Verified:** Official Flipkart Affiliate APIs exist (Product, Offer, Report)
  and the docs explicitly list "shopping comparison sites" as a use case.
  Source: https://affiliate.flipkart.com/api-docs/af_overview.html
- **Verified:** Access requires registering as an affiliate, then generating an
  API token. Requests send `Fk-Affiliate-Id` and `Fk-Affiliate-Token` headers.
  Source: https://affiliate.flipkart.com/api-docs/af_register.html
- **Verified:** Documented rate limit is 20 calls/second per affiliate; product
  feed URLs expire within 10 hours.
  Source: https://affiliate.flipkart.com/api-docs/af_faq.html
- **Verified:** A keyword search endpoint and a product-by-ID endpoint exist;
  the glossary lists versioned paths (`/affiliate/search/json`,
  `/affiliate/1.0/search/json`).
- **Unverified:** Which version is current, the exact response schema, whether
  new affiliates are being approved in 2026, and the Terms of Use details.
  Fetch the live docs and capture real fixtures before writing the adapter.
- **Open question:** Affiliate feeds usually expose listed price and discount;
  delivery charge, return policy, and warranty fields may be absent. The domain
  model must treat them as `unknown`, not zero.

## Uber (Moto)

- **Verified:** Uber's public developer docs describe a legacy Ride Requests
  estimate endpoint with a deprecation notice (Dec 10, 2022) and a "FULL ACCESS"
  approval process for broad distribution.
  Source: https://developer.uber.com/docs/riders/references/api/v1/requests-estimate-post
- **Unverified:** Whether any current Uber API returns Moto fare estimates in
  India for a third-party app. Several aggregator sites list Uber's API but
  these are not authoritative.
- **Consequence:** Treat as partner-only. Requires a business relationship.

## Rapido

- **Not found:** No official public developer API for fare estimates.
- **Found but rejected:** A community "skill" claims a Rapido integration
  "reverse-engineered from Rapido PWA". Using undocumented private endpoints
  conflicts with the project's rule to use only authorized, documented access,
  and would likely violate Rapido's terms. **Do not use.**
- **Consequence:** Partner outreach is the only compliant route.

## Decisions

1. The MVP runs entirely on **mock providers**. It will not be described as a
   live multi-vendor product (see PRD, Definition of Done).
2. The first real integration attempted will be **Flipkart Affiliate API**,
   because it is the only candidate with documented, self-serve registration.
   It starts only after the owner supplies credentials.
3. Amazon follows once Creators API eligibility is confirmed.
4. Transportation providers stay mock-only until a partner agreement exists.
   The transport category is deferred past the MVP.
5. Adapters for blocked providers are registered as `UNAVAILABLE` with a reason,
   never silently backed by synthetic data.

## Next verification steps (owner action)

- [ ] Register as a Flipkart affiliate; generate a token; share via env var only.
- [ ] Check Amazon Associates dashboard for Creators API access (India).
- [ ] Read each provider's Terms regarding price-comparison use and caching.
