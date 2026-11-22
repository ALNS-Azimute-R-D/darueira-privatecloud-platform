plugins {
    id("org.jetbrains.kotlin.jvm") version "1.9.21"
    id("org.jetbrains.kotlin.plugin.allopen") version "1.9.21"
    id("org.jetbrains.kotlin.kapt") version "1.9.21"
    id("groovy")
    id("io.micronaut.application") version "4.2.0"
}

repositories {
    mavenCentral()
}

dependencies {
    kapt("io.micronaut.data:micronaut-data-processor")
    kapt("io.micronaut:micronaut-http-validation")
    kapt("io.micronaut.openapi:micronaut-openapi")
    kapt("io.micronaut.serde:micronaut-serde-processor")
    kapt("io.micronaut.security:micronaut-security-annotations")
    kapt("io.micronaut.validation:micronaut-validation-processor")

    compileOnly("io.micronaut.openapi:micronaut-openapi-annotations")
    implementation("io.micronaut:micronaut-http-client")
    implementation("io.micronaut.data:micronaut-data-jdbc")
    implementation("io.micronaut.flyway:micronaut-flyway")
    implementation("io.micronaut.rabbitmq:micronaut-rabbitmq")
    implementation("io.micronaut.serde:micronaut-serde-jackson")
    implementation("io.micronaut.security:micronaut-security-jwt")
    implementation("io.micronaut.validation:micronaut-validation")
    implementation("jakarta.persistence:jakarta.persistence-api:3.1.0")
    implementation("io.projectreactor:reactor-core")

    runtimeOnly("org.yaml:snakeyaml")
    runtimeOnly("ch.qos.logback:logback-classic")
    runtimeOnly("io.micronaut.sql:micronaut-jdbc-hikari")
    runtimeOnly("mysql:mysql-connector-java")
    runtimeOnly("org.flywaydb:flyway-mysql")

    testImplementation("io.micronaut.test:micronaut-test-spock")
    testImplementation("org.testcontainers:mysql")
    testImplementation("org.testcontainers:spock")
    testImplementation("org.testcontainers:testcontainers")
    testImplementation("org.apache.groovy:groovy:4.0.16")
    testImplementation("org.apache.groovy:groovy-json:4.0.16")
    testRuntimeOnly("org.spockframework:spock-core:2.3-groovy-4.0")

    configurations.all {
        resolutionStrategy.eachDependency {
            if (requested.group == "org.codehaus.groovy" || requested.group == "org.apache.groovy") {
                useVersion("4.0.16")
            }
        }
    }
}

application {
    mainClass.set("de.legalhub.ApplicationKt")
}

java {
    sourceCompatibility = JavaVersion.toVersion("17")
}

tasks {
    compileKotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
    compileTestKotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
}

graalvmNative.toolchainDetection.set(false)

micronaut {
    runtime("netty")
    testRuntime("spock2")
    processing {
        incremental(true)
        annotations("de.legalhub.*")
    }
}

allOpen {
    annotation("io.micronaut.aop.Around")
    annotation("jakarta.inject.Singleton")
    annotation("io.micronaut.http.annotation.Controller")
    annotation("jakarta.transaction.Transactional")
}

kapt {
    arguments {
        arg("micronaut.openapi.views.spec", "swagger-ui.enabled=true,swagger-ui.theme=flattop")
    }
}

