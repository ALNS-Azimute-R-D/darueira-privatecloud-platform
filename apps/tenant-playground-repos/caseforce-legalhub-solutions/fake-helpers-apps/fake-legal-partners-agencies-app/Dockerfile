# ==============================================================================
# fake-legal-partners-agencies-app - Spring Boot partner-agency simulator (build context: this folder)
# ==============================================================================
# Build Stage. WORKDIR is /src on purpose: Tekton mounts a volume at /workspace and Kaniko leaves mount points out
# of cached layers, which breaks `COPY --from` on a warm cache (see backlog item 37).
FROM maven:3.9.9-eclipse-temurin-17-alpine AS builder

WORKDIR /src
COPY pom.xml .
RUN mvn dependency:go-offline -B

COPY src ./src
RUN mvn clean package -DskipTests -B

# ==============================================================================
# Runtime Stage (non-root, minimal JRE)
# ==============================================================================
FROM eclipse-temurin:17-jre-alpine

# Unprivileged UID 10001 (Pod Security Standards restricted)
RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira

WORKDIR /app
# The H2 file database lives in ./data (jdbc:h2:file:./data/fake_agency_db), so it must be writable by 10001.
RUN mkdir -p /app/data && chown -R 10001:10001 /app

COPY --from=builder --chown=10001:10001 /src/target/fake-legal-partners-agencies-app-*.jar /app/app.jar

USER 10001:10001

EXPOSE 8085

ENV JAVA_OPTS="-XX:+UseG1GC -XX:MaxRAMPercentage=75.0"

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
