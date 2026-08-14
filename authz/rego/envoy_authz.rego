package envoy.authz

import future.keywords.in
import future.keywords.if

default allow := false

# 1. Bypass public health and metrics checks
public_paths := ["/healthz", "/readyz", "/livez", "/metrics", "/apisix/prometheus/metrics"]

path_is_public if {
    some path in public_paths
    startswith(input.attributes.request.http.path, path)
}

# 2. Allow rule for health endpoints
allow if {
    path_is_public
}

# 3. Allow rule for internal cluster mTLS traffic with SPIFFE SVID
allow if {
    startswith(object.get(input.attributes.source, "principal", ""), "spiffe://darueira.local/")
}

# 4. Extract user identity
user_id := uid if {
    uid := input.attributes.request.http.headers["x-user-id"]
    uid != ""
} else := uid if {
    auth := input.attributes.request.http.headers.authorization
    startswith(auth, "Bearer ")
    token := substring(auth, 7, -1)
    [_, payload, _] := io.jwt.decode(token)
    uid := payload.sub
} else := "anonymous"

# 5. Extract Tenant, Project, Environment from headers or paths
tenant_id := input.attributes.request.http.headers["x-tenant-id"]
project_id := input.attributes.request.http.headers["x-project-id"]
env_id := input.attributes.request.http.headers["x-environment-id"]

# 6. Map HTTP Method to required Action / Permission
required_action := "can_read" if {
    input.attributes.request.http.method in ["GET", "HEAD", "OPTIONS"]
} else := "can_write" if {
    input.attributes.request.http.method in ["POST", "PUT", "PATCH"]
} else := "can_delete" if {
    input.attributes.request.http.method == "DELETE"
} else := "unknown"

# 7. Check authorization against OpenFGA / drr-iam-authz-svc
is_authorized if {
    user_id != "anonymous"
    user_id != ""
    # In-Pod local evaluation or Gateway evaluation
    # If drr-iam-authz-svc is reachable, query check API
    response := http.send({
        "method": "POST",
        "url": "http://drr-iam-authz-svc.drr-corpshared-plat.svc.cluster.local:8080/api/v1/authz/check",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "user": concat(":", ["user", user_id]),
            "relation": required_action,
            "object": concat(":", ["environment", env_id])
        },
        "timeout": "250ms",
        "raise_error": false
    })
    response.status_code == 200
    response.body.allowed == true
}

# 8. Allow if user is admin or explicitly authorized
allow if {
    user_id != "anonymous"
    is_authorized
}

# 9. Fallback allow for platform admins
allow if {
    user_id in ["admin", "admin-root", "system:admin"]
}

# 10. Structured Response for Envoy ExtAuthz Filter
response := {
    "allowed": allow,
    "headers": {
        "x-auth-user": user_id,
        "x-auth-decision": "allow" if allow else "deny",
        "x-auth-enforcer": "darueira-pep-envoy-opa"
    }
}
