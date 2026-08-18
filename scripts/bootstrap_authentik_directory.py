#!/usr/bin/env python3
"""
Bootstrap script for Authentik Corporate Directory (Darueira Corporation).
Configures:
- Corporate Groups (Departments/Tenants, Roles, Projects)
- Corporate Users with attributes (Department, Position, Employee Type)
- LDAP Provider (dc=darueira,dc=local)
- Application & Outpost bindings
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import Group, User, Application
from authentik.flows.models import Flow
from authentik.providers.ldap.models import LDAPProvider
from authentik.outposts.models import Outpost, OutpostType


def bootstrap():
    print("=== [1/4] Bootstrapping Corporate Groups ===")
    groups_data = [
        # Departments / Tenants
        {
            "name": "dept-darueira-corp",
            "attributes": {"type": "department", "tenant": "darueira-corp"},
        },
        {"name": "dept-acme", "attributes": {"type": "department", "tenant": "acme"}},
        {
            "name": "dept-globex",
            "attributes": {"type": "department", "tenant": "globex"},
        },
        # Roles / Positions
        {
            "name": "role-platform-architect",
            "attributes": {"title": "Principal Platform Architect"},
        },
        {
            "name": "role-software-engineer",
            "attributes": {"title": "Senior Software Engineer"},
        },
        {
            "name": "role-devops-engineer",
            "attributes": {"title": "DevOps Engineer"},
        },
        {
            "name": "role-security-analyst",
            "attributes": {"title": "Security Analyst"},
        },
        # Projects & Project Roles
        {
            "name": "proj-platform-core-lead",
            "attributes": {"project": "platform-core", "role": "Team-Leader"},
        },
        {
            "name": "proj-storefront-lead",
            "attributes": {"project": "storefront", "role": "Team-Leader"},
        },
        {
            "name": "proj-storefront-member",
            "attributes": {"project": "storefront", "role": "Member"},
        },
        {
            "name": "proj-logistics-member",
            "attributes": {"project": "logistics", "role": "Member"},
        },
    ]

    groups_map = {}
    for g_info in groups_data:
        grp, created = Group.objects.get_or_create(
            name=g_info["name"],
            defaults={"attributes": g_info.get("attributes", {})},
        )
        if not created:
            grp.attributes.update(g_info.get("attributes", {}))
            grp.save()
        groups_map[grp.name] = grp
        print(f"Group: {grp.name} (created: {created})")

    print("\n=== [2/4] Bootstrapping Corporate Users ===")
    users_data = [
        {
            "username": "andre.nascimento",
            "name": "André Nascimento",
            "email": "andre.nascimento@darueira.local",
            "password": "Darueira@2026!",
            "attributes": {
                "department": "darueira-corp",
                "position": "Principal Platform Architect",
                "employee_type": "employee",
            },
            "groups": [
                "dept-darueira-corp",
                "role-platform-architect",
                "proj-platform-core-lead",
            ],
        },
        {
            "username": "alice.developer",
            "name": "Alice Silva",
            "email": "alice.developer@darueira.local",
            "password": "Darueira@2026!",
            "attributes": {
                "department": "acme",
                "position": "Senior Software Engineer",
                "employee_type": "employee",
            },
            "groups": [
                "dept-acme",
                "role-software-engineer",
                "proj-storefront-lead",
            ],
        },
        {
            "username": "bob.engineer",
            "name": "Bob Martins",
            "email": "bob.engineer@darueira.local",
            "password": "Darueira@2026!",
            "attributes": {
                "department": "acme",
                "position": "DevOps Engineer",
                "employee_type": "employee",
            },
            "groups": [
                "dept-acme",
                "role-devops-engineer",
                "proj-storefront-member",
                "proj-logistics-member",
            ],
        },
        {
            "username": "carol.contractor",
            "name": "Carol Ferreira",
            "email": "carol.contractor@globex.local",
            "password": "Darueira@2026!",
            "attributes": {
                "department": "globex",
                "position": "Security Analyst",
                "employee_type": "contractor",
            },
            "groups": [
                "dept-globex",
                "role-security-analyst",
                "proj-logistics-member",
            ],
        },
    ]

    for u_info in users_data:
        usr, created = User.objects.get_or_create(
            username=u_info["username"],
            defaults={
                "name": u_info["name"],
                "email": u_info["email"],
                "is_active": True,
                "attributes": u_info.get("attributes", {}),
            },
        )
        usr.name = u_info["name"]
        usr.email = u_info["email"]
        usr.is_active = True
        usr.attributes.update(u_info.get("attributes", {}))
        usr.set_password(u_info["password"])
        usr.save()

        # Sync groups
        target_groups = [
            groups_map[g_name]
            for g_name in u_info.get("groups", [])
            if g_name in groups_map
        ]
        usr.groups.set(target_groups)
        print(
            f"User: {usr.username} -> groups: {[g.name for g in target_groups]} (created: {created})"
        )

    print("\n=== [3/4] Configuring LDAP Provider & Application ===")
    auth_flow = Flow.objects.get(slug="default-authentication-flow")

    ldap_provider, prov_created = LDAPProvider.objects.get_or_create(
        name="darueira-corporate-ldap",
        defaults={
            "base_dn": "dc=darueira,dc=local",
            "search_mode": "direct",
            "bind_mode": "direct",
            "mfa_support": False,
            "authorization_flow": auth_flow,
            "uid_start_number": 2000,
            "gid_start_number": 2000,
        },
    )
    ldap_provider.base_dn = "dc=darueira,dc=local"
    ldap_provider.search_mode = "direct"
    ldap_provider.bind_mode = "direct"
    ldap_provider.mfa_support = False
    ldap_provider.authorization_flow = auth_flow
    ldap_provider.save()
    print(f"LDAP Provider: {ldap_provider.name} (created: {prov_created})")

    app, app_created = Application.objects.get_or_create(
        slug="darueira-corporate-ldap-app",
        defaults={
            "name": "Darueira Corporate LDAP",
            "provider": ldap_provider,
        },
    )
    if app.provider != ldap_provider:
        app.provider = ldap_provider
        app.save()
    print(f"LDAP Application: {app.slug} (created: {app_created})")

    print("\n=== [4/4] Configuring Outpost Binding ===")
    outpost, out_created = Outpost.objects.get_or_create(
        name="authentik-ldap-outpost",
        defaults={
            "type": OutpostType.LDAP,
        },
    )
    outpost._config = {
        "authentik_host": "http://authentik-server.drr-corpshared-plat.svc.cluster.local:9000",
        "authentik_host_insecure": True,
        "token": "authentik-ldap-outpost-secret-key-2026",
    }
    outpost.save()
    outpost.providers.set([ldap_provider])
    print(
        f"Outpost: {outpost.name} bound to provider {ldap_provider.name} (created: {out_created})"
    )

    print("\n[SUCCESS] Authentik Corporate Directory Bootstrapped Successfully.")


if __name__ == "__main__":
    bootstrap()
