package envoy.authz_test

import data.envoy.authz

test_allow_public_healthz {
    authz.allow with input as {
        "attributes": {
            "request": {
                "http": {
                    "method": "GET",
                    "path": "/healthz",
                    "headers": {}
                }
            }
        }
    }
}

test_allow_public_metrics {
    authz.allow with input as {
        "attributes": {
            "request": {
                "http": {
                    "method": "GET",
                    "path": "/metrics",
                    "headers": {}
                }
            }
        }
    }
}

test_deny_anonymous_protected_path {
    not authz.allow with input as {
        "attributes": {
            "request": {
                "http": {
                    "method": "GET",
                    "path": "/api/v1/orders",
                    "headers": {}
                }
            }
        }
    }
}

test_allow_admin_user {
    authz.allow with input as {
        "attributes": {
            "request": {
                "http": {
                    "method": "POST",
                    "path": "/api/v1/deploy",
                    "headers": {
                        "x-user-id": "admin-root"
                    }
                }
            }
        }
    }
}

test_allow_spiffe_internal_mtls {
    authz.allow with input as {
        "attributes": {
            "source": {
                "principal": "spiffe://darueira.local/ns/drr-corpshared-plat/sa/tenant-svc"
            },
            "request": {
                "http": {
                    "method": "GET",
                    "path": "/internal/v1/status",
                    "headers": {}
                }
            }
        }
    }
}
