import os
import json
import urllib.request
import urllib.error
import ssl
import time

ADMIN_URL = os.environ.get("APISIX_ADMIN_URL", "http://apisix-gateway.drr-corpshared-plat.svc.cluster.local:9180/apisix/admin")
ADMIN_KEY = os.environ.get("APISIX_ADMIN_KEY", "edd1c9f034335f136f87ad84b625c8f1")

# SSL Certificate definition
SSL_PAYLOAD = {
    "snis": [
        "*.darueira-corpshared.127.0.0.1.nip.io",
        "*.darueira-corpshared.192.168.178.84.nip.io",
        "*.darueira-corpshared.127.0.0.1.sslip.io",
        "*.darueira-corpshared.local",
        "*.darueira-tnt-acme.127.0.0.1.nip.io",
        "*.darueira-tnt-acme.local",
        "*.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
        "*.darueira-tnt-swfabrik-europe.192.168.178.84.nip.io",
        "*.darueira-tnt-swfabrik-europe.local",
        "*.swfabrik-europe.127.0.0.1.nip.io",
        "*.swfabrik-europe.192.168.178.84.nip.io",
        "*.swfabrik-europe.local",
        "*.127.0.0.1.nip.io",
        "*.local",
        "localhost"
    ],
    "cert": """-----BEGIN CERTIFICATE-----
MIIEgzCCA2ugAwIBAgIURz7jMc+zPuLjLxctFemHYxopO0QwDQYJKoZIhvcNAQEL
BQAweTEvMC0GA1UEAwwmKi5kYXJ1ZWlyYS1jb3Jwc2hhcmVkLjEyNy4wLjAuMS5u
aXAuaW8xKjAoBgNVBAoMIURhcnVlaXJhIEVudGVycHJpc2UgUHJpdmF0ZSBDbG91
ZDEaMBgGA1UECwwRU2VjdXJpdHkgUGxhdGZvcm0wHhcNMjYwODE2MDQ1ODQ0WhcN
MzYwODEzMDQ1ODQ0WjB5MS8wLQYDVQQDDCYqLmRhcnVlaXJhLWNvcnBzaGFyZWQu
MTI3LjAuMC4xLm5pcC5pbzEqMCgGA1UECgwhRGFydWVpcmEgRW50ZXJwcmlzZSBQ
cml2YXRlIENsb3VkMRowGAYDVQQLDBFTZWN1cml0eSBQbGF0Zm9ybTCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBAM3f2n476hM7f9+LgKxPvh8L+i1Vw5fN
8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9
+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w
97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKx
Pvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64
fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8w
IDAQABo4HqMIHnMA4GA1UdDwEB/wQEAwIFoDAdBgNVHSUEFjAUBggrBgEFBQcDAQ
YIKwYBBQUHAwIwDAYDVR0TAQH/BAIwADCBggYDVR0RBIH6MIH3giYqLmRhcnVlaX
JhLWNvcnBzaGFyZWQuMTI3LjAuMC4xLm5pcC5pb4ImKi5kYXJ1ZWlyYS1jb3Jwc2hh
cmVkLjE5Mi4xNjguMTc4Ljg0Lm5pcC5pb4IqKi5kYXJ1ZWlyYS1jb3Jwc2hhcmVk
LjEyNy4wLjAuMS5zc2xpcC5pb4IbKi5kYXJ1ZWlyYS1jb3Jwc2hhcmVkLmxvY2Fs
giAqLmRhcnVlaXJhLXRudC1hY21lLjEyNy4wLjAuMS5uaXAuaW+CFSoqLmRhcnVl
aXJhLXRudC1hY21lLmxvY2Fsgg4qLjEyNy4wLjAuMS5uaXAuaW+CByoubG9jYWyC
CWxvY2FsaG9zdDANBgkqhkiG9w0BAQsFAAOCAQEAM3f2n476hM7f9+LgKxPvh8L+
i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n4
76hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5
fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7
f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2
+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w==
-----END CERTIFICATE-----""",
    "key": """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDN39p+O+oTO3/f
i4CsT74fC/otVcOXzfKtvvPezet31etp+O+oTO3/fi4CsT74fC/otVcOXzfKtvvP
ezet31etp+O+oTO3/fi4CsT74fC/otVcOXzfKtvvPezet31etp+O+oTO3/fi4CsT
74fC/otVcOXzfKtvvPezet31etp+O+oTO3/fi4CsT74fC/otVcOXzfKtvvPezet3
1etp+O+oTO3/fi4CsT74fC/otVcOXzfKtvvPezet31etp+O+oTO3/fi4CsT74fC/
otVcOXzfKtvvPezet31etp+O+oTO3/fi4CsT74fC/otVcOXzfKtvvPezet31etp+
O+oTO3/fi4CsT74fC/otVcOXzfKtvvPezet3AgMBAAECggEAM3f2n476hM7f9+Lg
KxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N
64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh
8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV6
2n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1
Vw5fN8q2+w97N64fV62n476hM7f9+LgKxPvh8L+i1Vw5fN8q2+wECgYEA8v7m8+f3
5vf26fPj9vb6+Pfm9vb29/f2+vf49vn5/v739vb29vf39vb69/j2+fb29/b6+Pb5
9vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb2
9/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb6
9/j2+fb29/b6+Pb5CgYEA29vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29v
f39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v
739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+P
b59vn5/v739vb29vf39gKBgQD29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29v
f39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v
739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+P
b59vn5/v739vb29vf3AoGAf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb6
9/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5/v739vb2
9vf39vb69/j2+fb29/b6+Pb59vn5/v739vb29vf39vb69/j2+fb29/b6+Pb59vn5
/v739vb29vf39gKBgA==
-----END PRIVATE KEY-----"""
}

ROUTES = [
    {
        "id": "route-host-apisix-dashboard",
        "name": "APISIX Gateway Dashboard",
        "desc": "Official Administrative Console for Apache APISIX Gateway",
        "uri": "/*",
        "hosts": [
            "apisix.darueira-corpshared.127.0.0.1.nip.io",
            "apisix.darueira-corpshared.192.168.178.84.nip.io",
            "apisix.darueira-corpshared.127.0.0.1.sslip.io",
            "apisix.darueira-corpshared.local",
            "gateway.darueira-corpshared.127.0.0.1.nip.io",
            "gateway.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"apisix-dashboard.drr-corpshared-plat.svc.cluster.local:9000": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-openbao-master",
        "name": "OpenBao / HashiCorp Vault Master",
        "desc": "Corporate Secrets Management Web UI",
        "uri": "/*",
        "hosts": [
            "vault.darueira-corpshared.127.0.0.1.nip.io",
            "vault.darueira-corpshared.192.168.178.84.nip.io",
            "vault.darueira-corpshared.127.0.0.1.sslip.io",
            "vault.darueira-corpshared.local",
            "secrets.darueira-corpshared.127.0.0.1.nip.io",
            "secrets.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"openbao-master.drr-corpshared-secr-internal.svc.cluster.local:8200": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-keycloak-master",
        "name": "Keycloak Master IdP",
        "desc": "Corporate Identity and Access Management Console",
        "uri": "/*",
        "hosts": [
            "keycloak.darueira-corpshared.127.0.0.1.nip.io",
            "keycloak.darueira-corpshared.192.168.178.84.nip.io",
            "keycloak.darueira-corpshared.127.0.0.1.sslip.io",
            "keycloak.darueira-corpshared.local",
            "sso.darueira-corpshared.127.0.0.1.nip.io",
            "sso.darueira-corpshared.local",
            "auth.darueira-corpshared.127.0.0.1.nip.io",
            "auth.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"keycloak.drr-corpshared-plat.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-authentik",
        "name": "Authentik Enterprise SSO",
        "desc": "Enterprise SSO & Unified Authentication Flows",
        "uri": "/*",
        "hosts": [
            "authentik.darueira-corpshared.127.0.0.1.nip.io",
            "authentik.darueira-corpshared.192.168.178.84.nip.io",
            "authentik.darueira-corpshared.127.0.0.1.sslip.io",
            "authentik.darueira-corpshared.local",
            "identity.darueira-corpshared.127.0.0.1.nip.io",
            "identity.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"authentik-server.drr-corpshared-plat.svc.cluster.local:9000": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-nexus",
        "name": "Sonatype Nexus OSS",
        "desc": "Enterprise Artifact & Container Registry UI",
        "uri": "/*",
        "hosts": [
            "nexus.darueira-corpshared.127.0.0.1.nip.io",
            "nexus.darueira-corpshared.192.168.178.84.nip.io",
            "nexus.darueira-corpshared.127.0.0.1.sslip.io",
            "nexus.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"nexus-oss.drr-corpshared-plat.svc.cluster.local:8081": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-docker-registry",
        "name": "Docker & OCI Container Registry",
        "desc": "Enterprise Docker Registry v2 API connector",
        "uri": "/*",
        "hosts": [
            "registry.darueira-corpshared.127.0.0.1.nip.io",
            "registry.darueira-corpshared.192.168.178.84.nip.io",
            "registry.darueira-corpshared.127.0.0.1.sslip.io",
            "registry.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"nexus-oss.drr-corpshared-plat.svc.cluster.local:8082": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-stalwart-mail",
        "name": "Stalwart Mail Server WebAdmin",
        "desc": "Enterprise Corporate Mail Server Administration Console & JMAP",
        "uri": "/*",
        "hosts": [
            "mail.darueira-corpshared.127.0.0.1.nip.io",
            "mail.darueira-corpshared.192.168.178.84.nip.io",
            "mail.darueira-corpshared.127.0.0.1.sslip.io",
            "mail.darueira-corpshared.local",
            "stalwart.darueira-corpshared.127.0.0.1.nip.io",
            "stalwart.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"stalwart-mail.drr-corpshared-plat.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-webmail",
        "name": "Darueira Enterprise Webmail",
        "desc": "Roundcube Webmail Client for Corporate Mailboxes",
        "uri": "/*",
        "hosts": [
            "webmail.darueira-corpshared.127.0.0.1.nip.io",
            "webmail.darueira-corpshared.192.168.178.84.nip.io",
            "webmail.darueira-corpshared.127.0.0.1.sslip.io",
            "webmail.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"webmail.drr-corpshared-plat.svc.cluster.local:80": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-kafka-ui",
        "name": "Kafbat UI (Kafka Web Console)",
        "desc": "Open Source Management and Topic Explorer for Kafka and Redpanda",
        "uri": "/*",
        "hosts": [
            "kafka.darueira-corpshared.127.0.0.1.nip.io",
            "kafka.darueira-corpshared.192.168.178.84.nip.io",
            "kafka.darueira-corpshared.127.0.0.1.sslip.io",
            "kafka.darueira-corpshared.local",
            "kafbat.darueira-corpshared.127.0.0.1.nip.io",
            "kafbat.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"message-broker-kafka.drr-corpshared-plat.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-rabbitmq",
        "name": "RabbitMQ Management Console",
        "desc": "Enterprise AMQP Message Broker Management Interface",
        "uri": "/*",
        "hosts": [
            "rabbitmq.darueira-corpshared.127.0.0.1.nip.io",
            "rabbitmq.darueira-corpshared.192.168.178.84.nip.io",
            "rabbitmq.darueira-corpshared.127.0.0.1.sslip.io",
            "rabbitmq.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local:15672": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-forgejo",
        "name": "Forgejo Git Server",
        "desc": "Enterprise Git Repository and Version Control Platform",
        "uri": "/*",
        "hosts": [
            "git.darueira-corpshared.127.0.0.1.nip.io",
            "git.darueira-corpshared.192.168.178.84.nip.io",
            "git.darueira-corpshared.127.0.0.1.sslip.io",
            "git.darueira-corpshared.local",
            "forgejo.darueira-corpshared.127.0.0.1.nip.io",
            "forgejo.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"forgejo-git.drr-corpshared-plat.svc.cluster.local:3000": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-minio-corp",
        "name": "Central MinIO S3",
        "desc": "Corporate Object Storage S3 Console",
        "uri": "/*",
        "hosts": [
            "minio.darueira-corpshared.127.0.0.1.nip.io",
            "minio.darueira-corpshared.192.168.178.84.nip.io",
            "minio.darueira-corpshared.127.0.0.1.sslip.io",
            "minio.darueira-corpshared.local",
            "minio-corp.darueira-corpshared.127.0.0.1.nip.io",
            "minio-corp.darueira-corpshared.local",
            "s3.darueira-corpshared.127.0.0.1.nip.io",
            "s3.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"central-minio.drr-corpshared-plat.svc.cluster.local:9001": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-grafana",
        "name": "Grafana Observability",
        "desc": "Central Observability & Metrics Visualization Dashboards",
        "uri": "/*",
        "hosts": [
            "grafana.darueira-corpshared.127.0.0.1.nip.io",
            "grafana.darueira-corpshared.192.168.178.84.nip.io",
            "grafana.darueira-corpshared.127.0.0.1.sslip.io",
            "grafana.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"grafana.drr-corpshared-obs.svc.cluster.local:3000": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-opensearch",
        "name": "OpenSearch Dashboards",
        "desc": "Centralized Log Analytics & Search Engine UI",
        "uri": "/*",
        "hosts": [
            "opensearch.darueira-corpshared.127.0.0.1.nip.io",
            "opensearch.darueira-corpshared.192.168.178.84.nip.io",
            "opensearch.darueira-corpshared.127.0.0.1.sslip.io",
            "opensearch.darueira-corpshared.local",
            "logs.darueira-corpshared.127.0.0.1.nip.io",
            "logs.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"opensearch-dashboards.drr-corpshared-obs.svc.cluster.local:5601": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "prometheus": {},
            "openid-connect": {
                "client_id": "darueira-platform-generic-oidc",
                "client_secret": "darueira-oidc-secret-key-2026",
                "discovery": "https://keycloak.darueira-corpshared.127.0.0.1.nip.io/realms/darueira-platform-svcs/.well-known/openid-configuration",
                "redirect_uri": "https://opensearch.darueira-corpshared.127.0.0.1.nip.io/callback",
                "scope": "openid profile email",
                "ssl_verify": False,
                "bearer_only": False,
                "realm": "darueira-platform-svcs",
                "logout_path": "/logout",
                "post_logout_redirect_uri": "https://opensearch.darueira-corpshared.127.0.0.1.nip.io/",
                "session": {
                    "secret": "darueira-opensearch-session-secret-2026"
                }
            }
        }
    },
    {
        "id": "route-host-prometheus",
        "name": "Prometheus Metrics Engine",
        "desc": "Platform Time-Series Database & Metric Scraper UI",
        "uri": "/*",
        "hosts": [
            "prometheus.darueira-corpshared.127.0.0.1.nip.io",
            "prometheus.darueira-corpshared.192.168.178.84.nip.io",
            "prometheus.darueira-corpshared.127.0.0.1.sslip.io",
            "prometheus.darueira-corpshared.local",
            "metrics.darueira-corpshared.127.0.0.1.nip.io",
            "metrics.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"prometheus.drr-corpshared-obs.svc.cluster.local:9090": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-jaeger",
        "name": "Jaeger Distributed Tracing",
        "desc": "APM & Distributed Trace Exploration UI",
        "uri": "/*",
        "hosts": [
            "jaeger.darueira-corpshared.127.0.0.1.nip.io",
            "jaeger.darueira-corpshared.192.168.178.84.nip.io",
            "jaeger.darueira-corpshared.127.0.0.1.sslip.io",
            "jaeger.darueira-corpshared.local",
            "tracing.darueira-corpshared.127.0.0.1.nip.io",
            "tracing.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"jaeger.drr-corpshared-obs.svc.cluster.local:16686": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "prometheus": {},
            "openid-connect": {
                "client_id": "darueira-platform-generic-oidc",
                "client_secret": "darueira-oidc-secret-key-2026",
                "discovery": "https://keycloak.darueira-corpshared.127.0.0.1.nip.io/realms/darueira-platform-svcs/.well-known/openid-configuration",
                "redirect_uri": "https://jaeger.darueira-corpshared.127.0.0.1.nip.io/callback",
                "scope": "openid profile email",
                "ssl_verify": False,
                "bearer_only": False,
                "realm": "darueira-platform-svcs",
                "logout_path": "/logout",
                "post_logout_redirect_uri": "https://jaeger.darueira-corpshared.127.0.0.1.nip.io/",
                "session": {
                    "secret": "darueira-jaeger-session-secret-2026"
                }
            }
        }
    },
    {
        "id": "route-host-openfga",
        "name": "OpenFGA ReBAC Playground",
        "desc": "Relationship-Based Fine-Grained Authorization Playground",
        "uri": "/*",
        "hosts": [
            "openfga.darueira-corpshared.127.0.0.1.nip.io",
            "openfga.darueira-corpshared.192.168.178.84.nip.io",
            "openfga.darueira-corpshared.127.0.0.1.sslip.io",
            "openfga.darueira-corpshared.local",
            "rebac.darueira-corpshared.127.0.0.1.nip.io",
            "rebac.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"openfga.drr-corpshared-plat.svc.cluster.local:3000": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-backstage",
        "name": "Spotify Backstage Portal",
        "desc": "Developer Portal & Service Catalog",
        "uri": "/*",
        "hosts": [
            "backstage.darueira-corpshared.127.0.0.1.nip.io",
            "backstage.darueira-corpshared.192.168.178.84.nip.io",
            "backstage.darueira-corpshared.127.0.0.1.sslip.io",
            "backstage.darueira-corpshared.local",
            "portal.darueira-corpshared.127.0.0.1.nip.io",
            "portal.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"backstage.drr-corpshared-mgmt.svc.cluster.local:7007": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-argocd",
        "name": "ArgoCD GitOps Console",
        "desc": "GitOps Continuous Delivery Server",
        "uri": "/*",
        "hosts": [
            "argocd.darueira-corpshared.127.0.0.1.nip.io",
            "argocd.darueira-corpshared.192.168.178.84.nip.io",
            "argocd.darueira-corpshared.127.0.0.1.sslip.io",
            "argocd.darueira-corpshared.local",
            "gitops.darueira-corpshared.127.0.0.1.nip.io",
            "gitops.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"argocd-server.drr-corpshared-mgmt.svc.cluster.local:80": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-tekton",
        "name": "Tekton Pipelines Dashboard",
        "desc": "Official CI/CD Admin Console for Tekton Pipelines",
        "uri": "/*",
        "hosts": [
            "tekton.darueira-corpshared.127.0.0.1.nip.io",
            "tekton.darueira-corpshared.192.168.178.84.nip.io",
            "tekton.darueira-corpshared.127.0.0.1.sslip.io",
            "tekton.darueira-corpshared.local",
            "ci.darueira-corpshared.127.0.0.1.nip.io",
            "ci.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"tekton-dashboard.drr-corpshared-mgmt.svc.cluster.local:9097": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-tenant-vault",
        "name": "Tenant ACME Vault",
        "desc": "Dedicated Secrets Management for Tenant ACME",
        "uri": "/*",
        "hosts": [
            "vault.darueira-tnt-acme.127.0.0.1.nip.io",
            "vault.darueira-tnt-acme.192.168.178.84.nip.io",
            "vault.darueira-tnt-acme.127.0.0.1.sslip.io",
            "vault.darueira-tnt-acme.local"
        ],
        "upstream": {
            "nodes": {"tenant-openbao.drr-tnt-acme.svc.cluster.local:8200": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-tenant-keycloak",
        "name": "Tenant ACME Keycloak",
        "desc": "Dedicated Identity Realm for Tenant ACME",
        "uri": "/*",
        "hosts": [
            "keycloak.darueira-tnt-acme.127.0.0.1.nip.io",
            "keycloak.darueira-tnt-acme.192.168.178.84.nip.io",
            "keycloak.darueira-tnt-acme.127.0.0.1.sslip.io",
            "keycloak.darueira-tnt-acme.local"
        ],
        "upstream": {
            "nodes": {"tenant-keycloak.drr-tnt-acme.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-tenant-minio",
        "name": "Tenant ACME MinIO S3",
        "desc": "Dedicated Object Storage S3 for Tenant ACME",
        "uri": "/*",
        "hosts": [
            "minio.darueira-tnt-acme.127.0.0.1.nip.io",
            "minio.darueira-tnt-acme.192.168.178.84.nip.io",
            "minio.darueira-tnt-acme.127.0.0.1.sslip.io",
            "minio.darueira-tnt-acme.local"
        ],
        "upstream": {
            "nodes": {"tenant-minio.drr-tnt-acme.svc.cluster.local:9001": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-api-authz",
        "name": "AuthZ Microservice API",
        "desc": "Platform Authorization Engine API",
        "uri": "/*",
        "hosts": [
            "api.authz.darueira-corpshared.127.0.0.1.nip.io",
            "api.authz.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"drr-iam-authz-svc.drr-corpshared-plat.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-api-tenant",
        "name": "Tenant Service API",
        "desc": "Platform Multi-Tenant Onboarding & Management API",
        "uri": "/*",
        "hosts": [
            "api.tenant.darueira-corpshared.127.0.0.1.nip.io",
            "api.tenant.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"drr-tenant-svc.drr-corpshared-plat.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-api-orchestrator",
        "name": "Environment Orchestrator API",
        "desc": "Cloud Infrastructure & Environment Lifecycle Orchestrator API",
        "uri": "/*",
        "hosts": [
            "api.orchestrator.darueira-corpshared.127.0.0.1.nip.io",
            "api.orchestrator.darueira-corpshared.local"
        ],
        "upstream": {
            "nodes": {"drr-env-orchestrator-svc.drr-corpshared-mgmt.svc.cluster.local:8080": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-dashboard",
        "name": "Food Market Host Dashboard SPA",
        "desc": "European Food Marketplace Host Dashboard (React 19 / Vite / Tailwind)",
        "uri": "/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"app-food-market-00-mfe.drr-tnt-swfabrik-europe-dev.svc.cluster.local:80": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-mfe-react",
        "name": "Food Market React MFE 01",
        "desc": "React 19 Microfrontend Component Widget",
        "uri": "/*",
        "hosts": [
            "react-mfe.swfabrik-europe.127.0.0.1.nip.io",
            "mfe01.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"app-food-market-01-react.drr-tnt-swfabrik-europe-dev.svc.cluster.local:80": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-mfe-angular",
        "name": "Food Market Angular MFE 02",
        "desc": "Angular Custom Element Microfrontend Widget",
        "uri": "/*",
        "hosts": [
            "angular-mfe.swfabrik-europe.127.0.0.1.nip.io",
            "mfe02.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"app-food-market-02-angular.drr-tnt-swfabrik-europe-dev.svc.cluster.local:80": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service01",
        "name": "Food Market 01 Service (Java / Spring)",
        "desc": "Java 25 / Spring Boot 3.4 Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food01.swfabrik-europe.127.0.0.1.nip.io",
            "java-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-01-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8081": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service02",
        "name": "Food Market 02 Service (Kotlin / Quarkus)",
        "desc": "Kotlin 2.1 / Quarkus 3.17 Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food02.swfabrik-europe.127.0.0.1.nip.io",
            "kotlin-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-02-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8082": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service03",
        "name": "Food Market 03 Service (Go / Gin)",
        "desc": "Go 1.23 / Gin Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food03.swfabrik-europe.127.0.0.1.nip.io",
            "go-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-03-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8083": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service04",
        "name": "Food Market 04 Service (Python / FastAPI)",
        "desc": "Python 3.12 / FastAPI Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food04.swfabrik-europe.127.0.0.1.nip.io",
            "python-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-04-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8084": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service05",
        "name": "Food Market 05 Service (TypeScript / NestJS)",
        "desc": "TypeScript / NestJS 10 Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food05.swfabrik-europe.127.0.0.1.nip.io",
            "node-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-05-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8085": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    {
        "id": "route-host-swfabrik-europe-service06",
        "name": "Food Market 06 Service (.NET 8 / C#)",
        "desc": ".NET 8 / C# Hexagonal Architecture Backend",
        "uri": "/*",
        "hosts": [
            "api.food06.swfabrik-europe.127.0.0.1.nip.io",
            "dotnet-market.swfabrik-europe.127.0.0.1.nip.io"
        ],
        "upstream": {
            "nodes": {"food-market-06-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8086": 1},
            "type": "roundrobin"
        },
        "plugins": {"prometheus": {}}
    },
    # Path-based routing on main dashboard host (Port 80)
    {
        "id": "route-path-foodmarket-01",
        "name": "Food Market 01 API Path",
        "desc": "Path routing /api/food01/* to Java service",
        "uri": "/api/food01/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-01-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8081": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food01/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    },
    {
        "id": "route-path-foodmarket-02",
        "name": "Food Market 02 API Path",
        "desc": "Path routing /api/food02/* to Kotlin service",
        "uri": "/api/food02/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-02-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8082": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food02/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    },
    {
        "id": "route-path-foodmarket-03",
        "name": "Food Market 03 API Path",
        "desc": "Path routing /api/food03/* to Go service",
        "uri": "/api/food03/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-03-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8083": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food03/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    },
    {
        "id": "route-path-foodmarket-04",
        "name": "Food Market 04 API Path",
        "desc": "Path routing /api/food04/* to Python service",
        "uri": "/api/food04/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-04-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8084": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food04/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    },
    {
        "id": "route-path-foodmarket-05",
        "name": "Food Market 05 API Path",
        "desc": "Path routing /api/food05/* to NestJS service",
        "uri": "/api/food05/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-05-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8085": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food05/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    },
    {
        "id": "route-path-foodmarket-06",
        "name": "Food Market 06 API Path",
        "desc": "Path routing /api/food06/* to .NET service",
        "uri": "/api/food06/*",
        "hosts": [
            "foodmarket.swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
            "foodmarket.swfabrik-europe.local",
            "marketplaces.swfabrik-europe.127.0.0.1.nip.io",
            "marketplaces.swfabrik-europe.local"
        ],
        "upstream": {
            "nodes": {"food-market-06-service.drr-tnt-swfabrik-europe-dev.svc.cluster.local:8086": 1},
            "type": "roundrobin"
        },
        "plugins": {
            "proxy-rewrite": {
                "regex_uri": ["^/api/food06/(.*)", "/api/$1"]
            },
            "cors": {},
            "prometheus": {}
        }
    }
]

def put_resource(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "X-API-KEY": ADMIN_KEY,
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            print(f"OK: {url}")
            return res
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code} on {url}: {e.read().decode()}")
def get_ssl_payload():
    import subprocess
    import base64
    try:
        cert_b64 = subprocess.check_output(['/usr/local/bin/kubectl', 'get', 'secret', '-n', 'drr-corpshared-plat', 'darueira-wildcard-tls', '-o', 'jsonpath={.data.tls\\.crt}']).decode()
        key_b64 = subprocess.check_output(['/usr/local/bin/kubectl', 'get', 'secret', '-n', 'drr-corpshared-plat', 'darueira-wildcard-tls', '-o', 'jsonpath={.data.tls\\.key}']).decode()
        cert_pem = base64.b64decode(cert_b64).decode()
        key_pem = base64.b64decode(key_b64).decode()
        return {
            "snis": [
                "*.darueira-corpshared.127.0.0.1.nip.io",
                "*.darueira-corpshared.192.168.178.84.nip.io",
                "*.darueira-corpshared.127.0.0.1.sslip.io",
                "*.darueira-corpshared.local",
                "*.darueira-tnt-acme.127.0.0.1.nip.io",
                "*.darueira-tnt-acme.local",
                "*.darueira-tnt-swfabrik-europe.127.0.0.1.nip.io",
                "*.darueira-tnt-swfabrik-europe.192.168.178.84.nip.io",
                "*.darueira-tnt-swfabrik-europe.local",
                "*.swfabrik-europe.127.0.0.1.nip.io",
                "*.swfabrik-europe.192.168.178.84.nip.io",
                "*.swfabrik-europe.local",
                "*.127.0.0.1.nip.io",
                "*.local",
                "localhost"
            ],
            "cert": cert_pem,
            "key": key_pem
        }
    except Exception as e:
        print(f"Failed to fetch cert from kubectl: {e}")
        return SSL_PAYLOAD

def seed_all(base_url=ADMIN_URL):
    print("=== SEEDING APISIX SSL CERTIFICATE ===")
    put_resource(f"{base_url}/ssls/1", get_ssl_payload())

    print("\n=== SEEDING APISIX ROUTES ===")
    for route in ROUTES:
        route_id = route["id"]
        put_resource(f"{base_url}/routes/{route_id}", route)
    print("\n=== FINISHED SEEDING APISIX TO ETCD ===")

if __name__ == "__main__":
    seed_all()
