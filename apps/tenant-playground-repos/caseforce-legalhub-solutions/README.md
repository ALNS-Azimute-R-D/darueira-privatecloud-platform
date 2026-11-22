# CaseForce Backend - Case Study & Multi-Agency Simulation

## Overview

**CaseForce LegalHub** is a case management and event integration platform for law firms and legal partner agencies. This repository contains the complete implementation of the case study, including:

1. **`caseforce-legalhub-mgmt/`**: Core Micronaut 4 / Kotlin Backend Application
   - Clean / Hexagonal Architecture structure (`domains`, `adapters`, `shared`, `model`)
   - User, Group, and Group Membership Management CRUD APIs with RBAC permissions
   - Partner Agency Onboarding API with atomic webhook subscriptions setup
   - Legal Case and Action Management CRUD APIs
   - OpenAPI 3 & Swagger UI interactive documentation (`/swagger-ui`)
   - Event-driven Webhook Delivery Engine with HMAC-SHA256 signing and SSRF protection
   - Scheduled Background Job for automatic retry of failed webhook deliveries
   - Bulk Case Reassignment API with asynchronous job execution and RabbitMQ event publication
   - Spock 2.3 Integration Test Suite with real PostgreSQL 17 TestContainers (10 test specifications)
2. **`fake-helpers-apps/fake-legal-partners-agencies-app/`**: Multi-Agency Simulation Application
   - Built with Java 17/25, Spring Boot 3.4.1, Maven, and persistent H2 File Database + Web H2-Console
   - Dedicated DTO-driven simulator service and controllers
   - Multi-agency routing with path variable `{partnerAgencyId}` across all endpoints
   - Inbound HMAC-SHA256 signature verification (`X-Caseforce-Signature-256`)
   - Automated onboarding client with configurable CaseForce host
3. **`specs/` & Documentation**:
   - `specs/01-initial-spec.md`: Complete functional and technical requirements
   - `specs/02-PLAN.md`: Phase-by-phase implementation plan and milestones
   - `DECISIONS.md`: Comprehensive Architecture Decision Records (ADRs), security models, and tradeoffs
   - `TODO.md`: Detailed progress and deliverables checklist

---

## Project Structure

```
caseforce-legalhub-solutions/
├── caseforce-legalhub-mgmt/                  # Core Micronaut Backend Service
│   ├── build.gradle.kts
│   ├── gradlew
│   └── src/
│       ├── main/kotlin/de/legalhub/
│       │   ├── Application.kt
│       │   ├── adapters/                     # Hexagonal / Clean Architecture Adapters
│       │   │   ├── input/messaging/          # RabbitMQ Event Listeners (EntityEventListener)
│       │   │   ├── output/messaging/         # RabbitMQ Producers (RabbitEntityEventClient)
│       │   │   └── output/repository/        # Micronaut Data JDBC Repositories (tb_* tables)
│       │   ├── domains/                      # Core Business Domains
│       │   │   ├── account/                  # User, Group & Membership CRUD, DTOs & Services
│       │   │   ├── action/                   # Action CRUD & Business Logic
│       │   │   ├── auth/                     # JWT Authentication, RBAC & @NeedsPermission
│       │   │   ├── bulk/                     # Asynchronous Bulk Operations Engine
│       │   │   ├── legalcase/                # Legal Case CRUD & Business Logic
│       │   │   ├── partneragency/            # Partner Agency Onboarding & Management
│       │   │   └── webhook/                  # Subscriptions, Delivery Engine, Scheduled Retries & HMAC Signer
│       │   ├── model/                        # Domain Entities & Mappings (Hungarian tb_ notation)
│       │   └── shared/                       # Shared Cross-Cutting Components
│       │       └── messaging/                # RabbitMQ Channels, Topics & Event Models
│       ├── main/resources/
│       │   ├── application.yml               # Centralized configuration (Log INFO, Retry, RabbitMQ)
│       │   └── databasemigrations/           # Flyway V1-V5 migrations (Expand & Contract pattern)
│       └── test/groovy/de/legalhub/         # Spock Integration Test Suite (10 Specs, 49 Tests)
│
├── fake-helpers-apps/
│   └── fake-legal-partners-agencies-app/     # Multi-Agency Simulation App (Spring Boot 3.4 + H2)
│       ├── pom.xml
│       ├── data/                             # Persistent H2 file database storage
│       └── src/
│           ├── main/java/de/legalhub/fakeagency/
│           │   ├── FakeAgencyApplication.java
│           │   ├── config/                   # RestClient & Application Configuration
│           │   ├── controller/               # Multi-agency webhook receiver & simulator API
│           │   ├── dto/                      # Type-safe DTOs for Agencies and Webhooks
│           │   ├── model/                    # JPA Entities (SubscriptionConfig, ReceivedWebhookEvent)
│           │   ├── repository/               # Spring Data JPA Repositories
│           │   ├── security/                 # HmacSignatureVerifier
│           │   └── service/                  # Agency Simulator & Onboarding Service
│           ├── main/resources/application.yml
│           └── test/java/de/legalhub/fakeagency/
│
├── specs/                                    # Technical Specifications & Plans
│   ├── 01-initial-spec.md
│   ├── 02-PLAN.md
│   └── adr/
├── DECISIONS.md                              # Architectural Decisions & Rationale
├── TODO.md                                   # Task progress checklist
├── docker-compose.yml                        # Local PostgreSQL 17 & RabbitMQ infrastructure
└── AGY.md                                    # Agent configuration and workspace rules
```

---

## Running the Applications

### Prerequisites
- **JDK 17** (or 21/25)
- **Docker** & **Docker Compose**
- **Maven 3.9+**

---

### 1. Core Service: `caseforce-legalhub-mgmt`

#### Run Tests (Spock + PostgreSQL TestContainers)
```bash
cd caseforce-legalhub-mgmt
./gradlew test
```

#### Run Locally
```bash
# 1. Start PostgreSQL & RabbitMQ infrastructure (from repository root)
docker compose up -d

# 2. Run Micronaut application
cd caseforce-legalhub-mgmt
./gradlew run
```

- **Application URL:** `http://localhost:8080`
- **Swagger UI:** `http://localhost:8080/swagger-ui`
- **OpenAPI YAML Spec:** `http://localhost:8080/swagger/caseforce-legal-hub-api-1.0.0.yml`
- **RabbitMQ Management UI:** `http://localhost:15673` (user: `guest`, pass: `guest`)

---

### 2. Multi-Agency Simulator: `fake-legal-partners-agencies-app`

#### Run Tests
```bash
cd fake-helpers-apps/fake-legal-partners-agencies-app
mvn test
```

#### Run Locally
```bash
cd fake-helpers-apps/fake-legal-partners-agencies-app
mvn spring-boot:run
```

- **Application URL:** `http://localhost:8085`
- **H2 Web Console:** `http://localhost:8085/h2-console` (JDBC URL: `jdbc:h2:file:./data/fake_agency_db`, user: `sa`, pass: empty)
- **Key Simulator Endpoints:**
  - `POST /api/agencies/{partnerAgencyId}/webhooks/caseforce`: Webhook callback receiver with HMAC verification
  - `POST /api/agencies/onboard-to-caseforce`: Trigger complete partner agency onboarding with webhooks against CaseForce
  - `GET /api/agencies/{partnerAgencyId}/webhooks/events`: Query received webhook events for this agency
  - `GET /api/agencies/{partnerAgencyId}/config`: View partner agency subscription configuration

---

## API Summary & Key Endpoints

### 1. User, Group & Membership Management (`/users`, `/groups`)
- `POST /users` — Create user with credentials and roles
- `GET /users` — List active users
- `GET /users/{id}` — Get user details by ID
- `PUT /users/{id}` — Update user profile and roles
- `DELETE /users/{id}` — Soft delete user and unlink group memberships
- `GET /users/{userId}/groups` — List groups assigned to a user
- `POST /groups` — Create permission group
- `GET /groups` — List groups with aggregated active member counts
- `GET /groups/{id}` — Get group details and permissions
- `PUT /groups/{id}` — Update group name and permissions
- `DELETE /groups/{id}` — Delete group and associated memberships
- `POST /groups/{groupId}/members/{userId}` — Add user to group
- `DELETE /groups/{groupId}/members/{userId}` — Remove user from group
- `GET /groups/{groupId}/members` — List members of a group

### 2. Partner Agency Onboarding (`/partner-agencies`)
- `POST /partner-agencies/onboarding` — Atomically register a new Partner Agency along with its predefined webhook subscriptions, associated Legal Cases, Lawyer/Assignee Users (resolved by email to prevent duplicate accounts or created automatically), and nested Actions.
- `POST /partner-agencies/batch-onboarding` — Batch onboarding for a collection of Partner Agencies with full nested cases, users, and actions.

### 3. Webhook Subscriptions & Deliveries (`/webhooks`)
- `POST /webhooks/subscriptions` — Register new agency webhook endpoint
- `GET /webhooks/subscriptions/{id}` — Get subscription by ID
- `GET /webhooks/subscriptions?partnerAgencyId={id}` — List subscriptions (optionally filtered by agency)
- `PUT /webhooks/subscriptions/{id}` — Update target URL, event types, or status
- `DELETE /webhooks/subscriptions/{id}` — Soft delete subscription
- `GET /webhooks/deliveries/{id}` — View delivery details, response code, and error trace
- `GET /webhooks/deliveries?subscriptionId={id}&status={status}` — Query delivery history
- `POST /webhooks/deliveries/{id}/retry` — Manually retry a failed delivery

### 4. Bulk Operations (`/cases/bulk-reassign`)
- `POST /cases/bulk-reassign` — Trigger asynchronous bulk case reassignment by filter criteria
- `GET /cases/bulk-reassign/{jobId}` — Poll execution progress (`totalCount`, `processedCount`, `successCount`, `failedCount`)

---

## Architecture & Design Decisions

See [`DECISIONS.md`](./DECISIONS.md) for full architectural justifications covering:
- Hungarian database notation (`tb_`) and indexing strategy.
- Clean / Hexagonal Architecture package isolation.
- Event-driven decoupling of case changes from partner webhook invocations via RabbitMQ.
- Exponential backoff retry policies, scheduled jobs, and SSRF mitigation.
- Asynchronous bulk processing vs. synchronous limits.
