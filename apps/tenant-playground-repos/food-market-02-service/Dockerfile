# ==============================================================================
# Build Stage
# ==============================================================================
FROM maven:3.9.9-eclipse-temurin-21-alpine AS builder

WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B

COPY src ./src
RUN mvn clean package -DskipTests -B

# ==============================================================================
# Runtime Stage (Non-root, Minimal alpine JRE)
# ==============================================================================
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Run as unprivileged UID 10001 (PSS Restricted Compliance)
RUN addgroup -g 10001 darueira && \
    adduser -u 10001 -G darueira -s /bin/sh -D darueira && \
    chown -R darueira:darueira /app

USER 10001:10001

COPY --from=builder --chown=10001:10001 /app/target/quarkus-app/lib/ /app/lib/
COPY --from=builder --chown=10001:10001 /app/target/quarkus-app/*.jar /app/
COPY --from=builder --chown=10001:10001 /app/target/quarkus-app/app/ /app/app/
COPY --from=builder --chown=10001:10001 /app/target/quarkus-app/quarkus/ /app/quarkus/

EXPOSE 8082

ENV JAVA_OPTS="-XX:+UseG1GC -XX:MaxRAMPercentage=75.0"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/quarkus-run.jar"]
