# ==============================================================================
# caseforce-legalhub-mgmt - Micronaut 4 / Kotlin backend (build context: this folder)
# ==============================================================================
# Build Stage. WORKDIR is /src on purpose: Tekton mounts a volume at /workspace and Kaniko leaves mount points out
# of cached layers, which breaks `COPY --from` on a warm cache (see backlog item 37).
FROM gradle:8.4.0-jdk17 AS builder

WORKDIR /src
COPY settings.gradle.kts build.gradle.kts gradle.properties ./
COPY src ./src
# The integration tests need Docker (TestContainers), so the image build skips them.
RUN gradle --no-daemon -x test buildLayers

# ==============================================================================
# Runtime Stage (non-root, minimal JRE)
# ==============================================================================
FROM eclipse-temurin:17-jre-alpine

# Unprivileged UID 10001 (Pod Security Standards restricted)
RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira

WORKDIR /home/app

# Layers by change frequency: libraries first, application code last.
COPY --from=builder --chown=10001:10001 /src/build/docker/main/layers/libs /home/app/libs
COPY --from=builder --chown=10001:10001 /src/build/docker/main/layers/classes /home/app/classes
COPY --from=builder --chown=10001:10001 /src/build/docker/main/layers/resources /home/app/resources
COPY --from=builder --chown=10001:10001 /src/build/docker/main/layers/application.jar /home/app/application.jar

USER 10001:10001

EXPOSE 8080

ENV JAVA_OPTS="-XX:+UseG1GC -XX:MaxRAMPercentage=75.0"

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /home/app/application.jar"]
