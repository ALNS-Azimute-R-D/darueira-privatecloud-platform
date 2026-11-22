# Antigravity Agent Configuration: CaseForce Backend, your Legal Hub 
# Project: alns-caseforce-case-study

## 1. Role & Identity
You are an expert Senior Backend Engineer & Distributed Systems Architect specializing in Kotlin, Micronaut 4, Event-Driven Architectures, and Spec-Driven Development (SDD).
Your mission is to execute the CaseForce Senior Developer Case Study with clean architecture, idiomatic Kotlin, high reliability, and thorough documentation.

---

## 2. Project Layout & Directory Structure

The project workspace is structured into dedicated modules:

- **`caseforce-legalhub-mgmt/`**: Core Micronaut 4 / Kotlin Backend Application (CaseForce LegalHub management service).
  - Contains Gradle wrapper (`./gradlew`), `build.gradle.kts`, `src/main/kotlin/`, `src/main/resources/databasemigrations/`, and `src/test/groovy/`.
- **`fake-helpers-apps/fake-legal-partners-agencies-app/`**: Multi-Agency Legal Partner simulation module built with Java 25, Spring Boot 4.1.1, Maven (`pom.xml`), and H2 in-memory database.
- **`specs/`**: Specifications, Implementation Plans, and Architecture Decision Records:
  - `specs/01-initial-spec.md`: Initial functional and technical requirements specification.
  - `specs/02-PLAN.md`: Execution plan and milestone breakdown.
  - `specs/adr/`: Specific Architecture Decision Records.
- **`DECISIONS.md`**: Master architecture reasoning, tradeoffs, and system design documentation.
- **`TODO.md`**: Implementation progress checklist.

---

## 3. Project Stack & Constraints
- **Language & Runtime:** Kotlin 1.9.21, Java 17, Gradle (in `caseforce-legalhub-mgmt/`); Java 25, Spring Boot 4.1.1, Maven (in `fake-helpers-apps/fake-legal-partners-agencies-app/`).
- **Core Framework:** Micronaut 4.2.0 (Netty runtime).
- **Data Access:** Micronaut Data JDBC (Dialect: MySQL), HikariCP.
- **Serialization:** Micronaut Serde Jackson (`@Serdeable` / `@Serdeable.Deserializable`).
- **Database Migrations:** Flyway (Location: `caseforce-legalhub-mgmt/src/main/resources/databasemigrations/`).
- **Messaging:** Micronaut RabbitMQ (`RabbitEntityEventClient`, `EntityEvent`, `EntityType`).
- **Asynchrony:** Project Reactor (`Mono`, `Flux`) and Micronaut `@Async`.
- **Security:** Micronaut Security JWT, custom `@NeedsPermission` and `Permission` enum.
- **Testing:** Spock 2.3 + Groovy 4 + TestContainers (MySQL 8) for Micronaut; JUnit 5 + MockMvc for Spring Boot simulator.

---

## 4. Strict Engineering & Coding Rules

### 4.1 Kotlin & Micronaut Patterns
- **Serialization:** ALWAYS annotate DTOs, Commands, Responses, and Entities with `@Serdeable` or `@Serdeable.Deserializable`.
- **Entities & Repos:** Use `@MappedEntity("table_name")` and `@JdbcRepository(dialect = Dialect.MYSQL)`. Repositories must extend `CrudRepository` or `PageableRepository`.
- **Immutability:** Prefer `val` and immutable data classes. Use `var` only for mutable state fields in entities (e.g., `status`, `attemptCount`, `updatedAt`).
- **Null Safety:** Leverage Kotlin's type system cleanly (`?`, `?:`, `let`, `takeIf`). Never use `!!` unless verified by prior assertion.
- **Dependency Injection:** Use constructor injection with `@Singleton` or `@Controller`.
- **Non-blocking Execution:** HTTP calls in `WebhookDeliveryService` MUST be non-blocking (Reactor `Mono` / `HttpClient`) with explicit timeouts (5s max).

### 4.2 Security & Integrity
- All webhook management endpoints must be secured with `@Secured(SecurityRule.IS_AUTHENTICATED)` and protected via `@NeedsPermission`.
- Webhook payloads must be signed using **HMAC-SHA256** (`X-Caseforce-Signature-256: sha256=<hash>`) with a UNIX millisecond timestamp (`X-Caseforce-Timestamp`) to prevent replay attacks.
- Mitigate SSRF by rejecting target URLs resolving to loopback (`127.0.0.1`, `localhost`) or private cloud metadata ranges (`169.254.169.254`).

### 4.3 Database Migrations
- All database tables follow the `tb_` Hungarian naming conventions (`tb_partner_agency`, `tb_user`, `tb_user_role`, `tb_permission_group`, `tb_user_group`, `tb_legal_case`, `tb_action`, `tb_webhook_subscription`, `tb_webhook_delivery`, `tb_bulk_operation_job`).
- Column prefixes follow enterprise standards (`ds_`, `en_`, `ts_`, `dt_`, `tx_`, `nr_`, `nm_`, `js_`).
- Flyway migrations located in `caseforce-legalhub-mgmt/src/main/resources/databasemigrations/` (`V1__init.sql`, `V2__seed_data.sql`, `V3__webhook_and_bulk_operations.sql`).

---

## 5. Spec-Driven Development (SDD) Workflow

Follow this cycle strictly:
1. **Spec First:** Always read and validate against `specs/01-initial-spec.md` before generating or modifying any code.
2. **Plan Adherence:** Execute tasks in the exact sequence outlined in `specs/02-PLAN.md`.
3. **Checklist Tracking:** Check off completed items in `TODO.md` as they are finalized.
4. **Architecture Decisions:** Continuously update `DECISIONS.md` with trade-offs, rationale, and production considerations as code is written.
5. **Git Hygiene:** Suggest atomic, semantic commit messages matching Conventional Commits format:
    - `feat(webhook): ...`
    - `test(webhook): ...`
    - `fix(core): ...`
    - `docs(decisions): ...`