# TODO

This is your checklist. Work through these items in whatever order makes sense to you.

## Phase 0: OpenAPI 3 & Swagger UI Setup
- [x] Add `micronaut-openapi` dependencies and processor to `build.gradle.kts`
- [x] Configure Swagger UI view and static resource mapping in `application.yml`
- [x] Annotate `Application.kt` with `@OpenAPIDefinition` and JWT `@SecurityScheme`
- [x] Annotate existing controllers (`LegalCaseController`, `ActionController`) and test Swagger UI generation

## Part 1: Webhook Delivery System

- [x] Design the data model: webhook registration, delivery log (new migration + entities)
- [x] Create API endpoints for partner agencies to register/manage their webhook configurations
- [x] Consume entity events (from `RabbitEntityEventClient` / `EntityEvent`) and trigger webhook deliveries
- [x] Implement webhook delivery with retry logic for failed attempts
- [x] Log delivery attempts (success/failure, response status, timestamps)
- [x] Secure webhook payloads (e.g., HMAC signature so partners can verify authenticity)

## Part 2: Bulk Operations API (Optional Bonus)

- [x] Create an endpoint for bulk case reassignment (filter criteria + target lawyer)
- [x] Handle the fact that this may affect hundreds of cases (sync vs async decision)
- [x] Report results: how many succeeded, how many failed, why
- [x] Make sure each reassigned case triggers the normal entity events (so webhooks fire)

## Part 3: Connect the two systems (Optional — only if you implement Part 2)

- [x] Ensure bulk operations feed into the webhook system without tight coupling
- [x] Consider: what happens when 200 cases are reassigned at once? Does each partner agency get 200 separate webhooks? One batched webhook? Something else?

## Phase 8: Fake Legal Partner Agency Simulation Module (Bonus)
- [x] Initialize Maven + Spring Boot 4.1.1 + Java 25 project `fake-helpers-apps/fake-legal-partners-agencies-app` with H2 database
- [x] Implement Multi-Agency H2 entities (`PartnerSubscriptionConfig`, `ReceivedWebhookEvent`) and JPA repositories
- [x] Implement `HmacSignatureVerifier` and Webhook receiver endpoint (`POST /api/agencies/{partnerAgencyId}/webhooks/caseforce`)
- [x] Implement automated CaseForce subscription client (`POST /api/agencies/{partnerAgencyId}/subscribe`)
- [x] Expose agency-scoped received events query API (`GET /api/agencies/{partnerAgencyId}/webhooks/events`) and test multi-agency end-to-end integration

## Deliverables

- [x] Working code (compiles, key paths work — doesn't need to be production-perfect)
- [x] At least one integration test (follow the existing `LegalCaseControllerSpec` pattern)
- [x] Fill in `DECISIONS.md` with your architecture reasoning
- [x] If you notice issues in the existing code, mention them in `DECISIONS.md`
- [x] Commit as you go — the git history is part of the deliverable (semantic commit messages recommended)

