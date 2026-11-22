# Architecture & Technical Decisions

This document details the architectural decisions, trade-offs, security mechanisms, and design patterns adopted in the CaseForce LegalHub platform for the **OpenAPI 3 Documentation**, **Webhook Delivery System**, **Bulk Operations Engine**, and the **Fake Legal Partner Agency Simulation Module**.

---

## 1. Data Model & Database Naming Conventions

### 1.1 Database Naming Conventions (By my own)
In alignment with enterprise database standards, all database tables and columns follow strict Hungarian/type-prefix notation:
- **Tables**: `tb_partner_agency`, `tb_user`, `tb_user_role`, `tb_permission_group`, `tb_user_group`, `tb_legal_case`, `tb_action`, `tb_webhook_subscription`, `tb_webhook_delivery`, `tb_bulk_operation_job`.
- **Column Prefixes**:
  - `ds_`: Descriptors and string values (`ds_target_url`, `ds_secret`, `ds_job_type`, `ds_event_type`)
  - `en_`: Enumeration representations (`en_status`)
  - `dt_`: Date columns (``)
  - `ts_`: Timestamp columns (`ts_date_created`, `ts_date_updated`, `ts_date_deleted`, `ts_last_attempt_at`)
  - `nr_`: Integer counts and numerical codes (`nr_attempt_count`, `nr_response_status_code`, `nr_total_count`, `nr_processed_count`, `nr_success_count`, `nr_failed_count`, `nr_entity_id`)
  - `tx_`: Large text / multi-line payloads (`tx_response_body`, `tx_error_message`)
  - `js_`: Structured JSON documents (`js_event_types`, `js_payload`, `js_filter_criteria`, `js_error_summary`)

### 1.2 Schema Design & Indexing
1. **`tb_webhook_subscription`**:
   - `partner_agency_id` (FK to `tb_partner_agency(id)`): Multi-tenant agency boundary.
   - `ds_target_url`: HTTPS/HTTP callback URL.
   - `ds_secret`: Auto-generated or custom cryptographic secret key (`whsec_...`) used for HMAC-SHA256 signing.
   - `js_event_types`: JSON array of subscribed event types (`LEGAL_CASE_CREATED`, `LEGAL_CASE_UPDATED`, `ACTION_CREATED`, `ACTION_UPDATED`).
   - `en_status`: Status lifecycle (`ACTIVE`, `INACTIVE`, `SUSPENDED`).
   - `ts_date_deleted`: Soft-delete audit column.
   - **Indexes**: `idx_webhook_sub_agency` on `(partner_agency_id, en_status)` for sub-millisecond event-to-subscription fan-out lookups.

2. **`tb_webhook_delivery`**:
   - `subscription_id` (FK to `tb_webhook_subscription(id)`): Links attempt to registration.
   - `ds_event_type`, `ds_entity_type`, `nm_entity_id`: Event provenance metadata.
   - `js_payload`: JSON payload snapshot sent to the partner.
   - `en_status`: `PENDING`, `SUCCESS`, `FAILED`.
   - `nr_attempt_count`, `ts_last_attempt_at`, `nr_response_status_code`, `tx_response_body`, `tx_error_message`: Complete execution and failure diagnostics.
   - **Indexes**: `idx_webhook_deliv_sub` on `(subscription_id, ts_date_created)`, `idx_webhook_deliv_status` on `(en_status)` for dead-letter reprocessing.

3. **`tb_bulk_operation_job`**:
   - `ds_job_type`: `CASE_REASSIGNMENT`.
   - `en_status`: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`.
   - `requested_by_id`, `target_lawyer_id`: Foreign keys to `tb_user(id)`.
   - `js_filter_criteria`: Immutable JSON snapshot of request filters.
   - `nr_total_count`, `nr_processed_count`, `nr_success_count`, `nr_failed_count`, `js_error_summary`: Asynchronous execution progress and audit metrics.

### 1.3 Database Migration Strategy (Expand-and-Contract Pattern)
To simulate enterprise-grade zero-downtime schema evolution, database migrations were structured into a progressive 5-phase lifecycle:
- **`V1__init.sql`**: Baseline legacy schema (`partner_agency`, `user`, `user_role`, `permission_group`, `user_group`, `legal_case`, `action`).
- **`V2__seed_data.sql`**: Baseline initial seed data for the legacy tables.
- **`V3__create_all_with_naming_convention.sql`** *(Expand)*: Creates all target `tb_*` tables incorporating type-prefix Hungarian naming conventions (`ds_`, `en_`, `dt_`, `ts_`, `nr_`, `tx_`, `js_`), complete relational constraints, indexes, and new domain tables (`tb_webhook_subscription`, `tb_webhook_delivery`, `tb_bulk_operation_job`).
- **`V4__seed_data_after_renaming.sql`** *(Data Migration)*: Safely migrates and transforms existing rows from legacy tables into the new `tb_*` structure with fallback defaults (e.g., automated alias derivation).
- **`V5__drop_original_structure.sql`** *(Contract)*: Drops the original legacy tables once data migration is verified, ensuring the production database only retains the clean, standardized schema.

### 1.4 Entity Audit Properties & JPA Mapping Standard
Across all Kotlin domain entities:
- Standardized temporal audit attributes: `createdAt` (`ts_date_created`), `updatedAt` (`ts_date_updated`), and `deletedAt` (`ts_date_deleted`) using Micronaut Data `@DateCreated` / `@DateUpdated`.
- Standardized boolean flags: `enabled` (`is_enabled` on `tb_user`), `isTask` (`is_task` on `tb_action`).
- Explicit foreign key mappings: replaced raw column definitions with JPA `@JoinColumn` relationships (e.g., `UserGroup`, `UserRole`, `WebhookDelivery`).
- Clean Decoupled Model for Micronaut Data JDBC: `User` and `Group` are decoupled and managed explicitly via `UserGroup` (`@Table(name = "tb_user_group")`) and `UserGroupRepository`, avoiding AOT join overhead and JSON circular serialization recursion.

---

## 2. Event Flow: From Case Change to Webhook Delivery

### 2.1 Decoupled Architecture
```
[Client / Bulk Op]
        │
        ▼ (HTTP REST)
[LegalCaseController / BulkOperationService]
        │
        ├──> (Database Save / Commit)
        │
        └──> (RabbitMQ Publish: entity.events)
                    │
                    ▼ (Queue: entity.events)
        [EntityEventListener] (RabbitMQ Adapter)
                    │
                    ▼ (Domain Delegation)
        [WebhookEntityEventProcessor] (Webhook Domain)
                    │
                    ├──> (1) Resolve Partner Agency (case.partnerAgencyId)
                    ├──> (2) Lookup Active Subscriptions (tb_webhook_subscription)
                    ├──> (3) Build Canonical JSON Snapshot Payload
                    ├──> (4) Persist WebhookDelivery (PENDING)
                    │
                    ▼ (Async Dispatcher: TaskExecutors.BLOCKING)
        [WebhookDeliveryService]
                    │
                    ├──> Compute HMAC-SHA256 Signature Header
                    ├──> HTTP POST -> Partner Webhook Endpoint
                    └──> Update WebhookDelivery (SUCCESS / FAILED, Status Code, Body)
```

### 2.2 Why Asynchronous Event-Driven?
- **Zero Latency Overhead for Core Operations**: Case mutations return immediately to end users without being blocked by network latency or downtime from third-party partner servers.
- **Resilience to Transient Failures**: If partner webhook endpoints timeout or fail, the database transaction of the case itself is not rolled back.
- **Natural Fan-Out**: Multiple partner systems or analytics tools can register webhooks against the same platform events without modifying core business logic.

---

## 3. Webhook Delivery Reliability & Retries

### 3.1 Delivery Strategy & Timeout Bounds
- **HTTP Client**: Built with non-blocking Reactor `Mono` and bounded to a 5-second socket timeout to prevent thread starvation.
- **Payload Capture**: Incoming event state is serialized at event-generation time, preventing race conditions where later case edits might alter the snapshot delivered for earlier events.
- **Audit Logging**: Every request attempt updates `tb_webhook_delivery` with status code, response body (truncated to 1,000 characters to prevent database bloat), and error messages.

### 3.2 Error Classification & Exponential Backoff
- **Non-Retryable Errors** (`400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `410 Gone`, `422 Unprocessable Entity`): Marked as `FAILED` immediately without redundant retries.
- **Retryable Errors** (`500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`, Socket Timeouts): Handled through exponential backoff retry tiers (delays: 2s, 10s, 30s) up to `MAX_RETRIES = 3`.
- **Manual Retry API**: `POST /webhooks/deliveries/{id}/retry` allows operators and partner developers to re-trigger failed deliveries on demand after fixing their receiver endpoints.

---

## 4. Bulk Operations: Sync vs. Async Execution

### 4.1 Design Trade-off
- **Decision**: Hybrid asynchronous model. For typical bulk operations (e.g. 50–500 cases), the request is accepted with HTTP `202 Accepted` returning a `BulkOperationResponse` tracking object (`jobId`), and executed asynchronously across chunks.
- **Progress Tracking**: Callers can poll `GET /cases/bulk-reassign/{jobId}` to monitor live metrics (`processedCount`, `totalCount`, `successCount`, `failedCount`, `errorSummary`).
- **Failure Isolation**: Case updates are executed per case/chunk within separate transaction boundaries. If 1 case fails validation or database constraint, remaining cases continue to be processed and failures are aggregated in `js_error_summary`.

---

## 5. Connecting Bulk Operations to Webhooks

### 5.1 Avoiding Tight Coupling
- The `BulkOperationService` does not import or know about `WebhookDeliveryService` or `tb_webhook_delivery`.
- Instead, each successfully reassigned case emits an `EntityEvent(EntityType.LEGAL_CASE, caseId)` onto the RabbitMQ `entity.events` topic exchange.
- The `EntityEventListener` receives each event and delegates to `WebhookEntityEventProcessor` identically to single-case edits.
- **Scale Protection**: For high-volume bulk updates, deliveries are processed concurrently via Micronaut's managed thread pool (`TaskExecutors.BLOCKING`), ensuring RabbitMQ messages are acknowledged and webhook calls are decoupled from the bulk job thread.

---

## 6. Security & Defense in Depth

### 6.1 Cryptographic Authenticity (HMAC-SHA256)
- Each registered subscription receives a unique secret key (`whsec_...`).
- When CaseForce delivers a webhook, it calculates an HMAC-SHA256 signature over `"$timestamp.$payload"` using `WebhookSigner`.
- Delivered HTTP Headers:
  - `X-Caseforce-Signature-256`: `sha256=<hex_encoded_hmac>`
  - `X-Caseforce-Timestamp`: Unix millisecond timestamp
  - `X-Caseforce-Event`: Event name (`LEGAL_CASE_UPDATED`, etc.)
  - `X-Caseforce-Delivery-Id`: Unique delivery tracking ID
- Verification uses constant-time string/byte comparison (`MessageDigest.isEqual`) to eliminate side-channel timing attack vectors.

### 6.2 SSRF Protection (`UrlSecurityValidator`)
- Webhook target URLs are parsed and strictly validated before persistence.
- Supported schemes are strictly restricted to `http` and `https`.
- Resolves DNS and blocks internal cloud metadata IPs (`169.254.169.254`, `metadata.google.internal`), loopback addresses (`127.0.0.0/8`, `::1`), and RFC 1918 private subnets in production mode (`caseforce.webhooks.allow-private-ips: false`).

### 6.3 RBAC & Permission Enforcement
- Dedicated granular permissions added to `Permission` enum:
  - `WEBHOOK_CREATE`, `WEBHOOK_GET`, `WEBHOOK_UPDATE`, `WEBHOOK_DELETE`, `WEBHOOK_LIST`
  - `BULK_OPERATION_CREATE`, `BULK_OPERATION_GET`
- Protected at controller level using `@Secured` and `@NeedsPermission(...)`.

---

## 7. Issues Noticed in the Existing Codebase & Recommendations

1. **`Group.kt` Column Name Mismatch**:
   - `Group.kt` had `@Column(name = "ds_permissions")` while the database migration defined `js_permissions JSON`. This has been fixed to `@Column(name = "js_permissions")`.
2. **JPA vs. Micronaut Data JDBC Annotations**:
   - In Micronaut Data JDBC, `@JoinColumn` from JPA can cause association mapping ambiguities in some dialects; using `@Column(name = "...")` combined with `@ManyToOne` guarantees exact SQL column generation.
3. **OpenAPI Generation Configuration**:
   - Micronaut 4 OpenAPI processor requires explicit Gradle compiler arguments (`micronaut.openapi.views.spec`) and security annotations (`@SecurityScheme`) on the root application class to render Swagger UI correctly without runtime reflection.

---

## 8. What I Would Do Differently in Production

1. **Persistent Distributed Task Queue (Kafka / RabbitMQ DLQ / Quartz / Temporal)**:
   - For massive bulk operations (e.g. 100,000+ cases), utilize a distributed workflow orchestrator or partitioned Kafka topic with worker pods.
2. **Webhook Batching & Rate Limiting**:
   - Implement rate-limiting per partner endpoint (e.g. Token Bucket algorithm, max 50 req/sec) to avoid overwhelming partner servers during large bulk updates.
3. **Mutual TLS (mTLS) & IP Whitelisting**:
   - Provide enterprise partners with dedicated outbound egress static IPs and support for client certificate authentication.
4. **Automated Circuit Breaker**:
   - If a partner endpoint consistently fails for > 1,000 consecutive deliveries, automatically transition the subscription to `SUSPENDED` and email the partner technical contact.

---

## 9. Modular Project Restructuring & Simulator Isolation

### 9.1 Multi-Application Monorepo Layout
To support testing, simulation, and clean separation of concerns, the repository is organized into distinct domain boundaries:
1. **`caseforce-legalhub-mgmt/`**: Contains the core Micronaut 4 service, domain models, database migrations, and Spock integration test suite.
2. **`fake-helpers-apps/fake-legal-partners-agencies-app/`**: An independent Spring Boot 4.1.1 / Java 25 application designed to simulate one or more partner law firms subscribing to webhooks and receiving authenticated HTTP notifications with HMAC verification.
3. **`specs/`**: Centralized living documentation containing initial requirements, implementation milestones, and Architecture Decision Records (ADRs).

### 9.2 Rationale & Benefits
- **Zero Cross-Pollution of Dependencies**: The Micronaut Kotlin stack and Spring Boot Maven stack maintain completely decoupled build lifecycles and runtime dependencies.
- **Realistic Integration Testing**: Developers and testers can run both applications concurrently (`localhost:8080` and `localhost:8085`) to observe end-to-end webhook dispatch and HMAC signature verification in real time.

---

## 10. 3-Tier Webhook Resilience & Retry Architecture

To guarantee at-least-once delivery semantics for mission-critical webhook events while preserving throughput and resource isolation, a 3-tier resilience pipeline was implemented:

1. **Tier 1 - Immediate Asynchronous Auto-Retry with Exponential Backoff (`deliverWithAutoRetry`)**:
   - Event consumption from RabbitMQ triggers non-blocking execution on dedicated blocking worker threads (`@Async(TaskExecutors.BLOCKING)`).
   - On network timeout or HTTP 5xx failures, the worker automatically re-attempts delivery up to `max-attempts` times (default: 3) with configurable exponential backoff (`initial-backoff-ms` default: 1000ms, multiplier: 2.0).
   - Each retry recalculates the HMAC-SHA256 signature with a fresh timestamp header (`X-Webhook-Timestamp`), preventing replay vulnerability windows.
2. **Tier 2 - Scheduled Background Recovery Job (`WebhookRetryScheduledJob`)**:
   - A background job scheduled via Micronaut `@Scheduled(fixedDelay = "${webhook.retry.job.fixed-delay:5m}")` scans the database for `FAILED` deliveries where `attemptCount < jobMaxAttempts` (default: 10).
   - Automatically recovers webhooks that experienced partner-side downtime exceeding the Tier 1 immediate backoff window.
3. **Tier 3 - Operational / Manual Retry API (`POST /webhooks/deliveries/{id}/retry`)**:
   - For partner outages exceeding the automatic retry limits or disaster recovery scenarios, authorized operations staff can trigger on-demand redelivery via an authenticated, permission-protected endpoint (`@NeedsPermission(Permission.WEBHOOK_UPDATE)`).

All resilience parameters (`max-attempts`, `initial-backoff-ms`, `multiplier`, `job.enabled`, `job.fixed-delay`, `job.max-attempts`) are fully parameterized in `application.yml` and overridable via standard environment variables.

---

## 11. Enterprise Logging & Configuration Standards

- **Logback Configuration (`src/main/resources/logback.xml`)**: Standardized console appender formatted with timestamp, thread, level, logger name, and message, defaulted to `INFO` root level.
- **Dynamic Property Binding (`logger.levels` in `application.yml`)**: Allows runtime override of application, framework, security, and HTTP client log levels via environment variables (`LOG_LEVEL`, `LOG_LEVEL_APP`, `LOG_LEVEL_MICRONAUT`, `LOG_LEVEL_SECURITY`, `LOG_LEVEL_HTTP`).

---

## 12. Partner Agency Onboarding & Multi-Tenant Fake Simulation

### 12.1 Unified Atomic Onboarding (`POST /partner-agencies/onboarding`)
- **Single-Transaction Provisioning**: Enables simultaneous registration of a new `PartnerAgency` along with its full collection of initial `WebhookSubscription` items in one atomic `@Transactional` operation.
- **Alias Identification**: Partner agencies are assigned a unique alphanumeric slug/alias (e.g. `berlin-legal-partners`) in addition to their numeric auto-increment primary key ID.
- **Embedded Security Checks**:
  - Validates all provided webhook target URLs through `UrlSecurityValidator` to mitigate SSRF vulnerabilities (blocking loopback/private ranges in production while allowing customizable dev testing).
  - Automatically generates cryptographically strong HMAC secrets (`whsec_...`) if not explicitly supplied by the caller.

### 12.2 Multi-Agency Simulation in `fake-legal-partners-agencies-app`
- **Dynamic Multi-Partner Routing**: The Spring Boot simulator now supports arbitrary partner agencies distinguished by path parameter: `/api/agencies/{partnerAgencyAlias}/webhooks/caseforce`.
- **Onboarding Coordination**: Exposes `POST /api/agencies/onboard` (and `POST /api/agencies/{partnerAgencyAlias}/onboard`) to automatically register the agency on CaseForce and configure local HMAC verification.
- **Isolated Per-Agency Audit Log**: Incoming webhook events and signature verification results are isolated and queryable per agency via `GET /api/agencies/{partnerAgencyAlias}/webhooks/events`.

### 12.3 File-Based H2 Persistence & H2 Web Console
- **Persistent Local Database**: `fake-legal-partners-agencies-app` persists records directly to disk at `jdbc:h2:file:./data/fake_agency_db;DB_CLOSE_DELAY=-1;AUTO_SERVER=TRUE`, preserving registered agencies, HMAC secrets, and received webhook audit events across application restarts.
- **Embedded Web Console**: Enabled at `http://localhost:8085/h2-console` (`JDBC URL: jdbc:h2:file:./data/fake_agency_db`, `User: sa`, `Password: <blank>`), allowing developers and reviewers to inspect and manually query/edit database tables via browser.
- **Test Isolation**: Unit and integration test suites automatically execute against an isolated in-memory H2 database (`jdbc:h2:mem:fake_agency_test_db`), guaranteeing zero side-effects on disk data.

