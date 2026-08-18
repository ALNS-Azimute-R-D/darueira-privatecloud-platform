#!/usr/bin/env python3
"""
==============================================================================
Script: scripts/validate_stalwart_iam.py
Purpose: End-to-End Validation Suite for Stalwart Mail Server Integration
         with Authentik LDAP & Keycloak Central OIDC:
         - Tests Keycloak Direct Grant OIDC Token Issuance
         - Tests Stalwart JMAP Session & Mailbox Enumeration with Bearer Tokens
         - Tests Stalwart IMAP4rev2 XOAUTH2 Authentication with Bearer Tokens
         - Tests SMTP Mail Delivery & JMAP Real-Time Inbox Retrieval
==============================================================================
"""

import imaplib
import json
import os
import smtplib
import ssl
import sys
import time
import urllib.request
import urllib.parse
from email.mime.text import MIMEText

KEYCLOAK_TOKEN_URL = os.environ.get(
    "KEYCLOAK_TOKEN_URL",
    "http://keycloak.drr-corpshared-plat.svc.cluster.local:8080/realms/darueira-platform-svcs/protocol/openid-connect/token"
)
STALWART_HTTP_HOST = os.environ.get("STALWART_HTTP_HOST", "stalwart-mail.drr-corpshared-plat.svc.cluster.local:8080")
STALWART_IMAP_HOST = os.environ.get("STALWART_IMAP_HOST", "stalwart-mail.drr-corpshared-plat.svc.cluster.local")
STALWART_SMTP_HOST = os.environ.get("STALWART_SMTP_HOST", "stalwart-mail.drr-corpshared-plat.svc.cluster.local")

CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "darueira-platform-generic-oidc")
CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "darueira-oidc-secret-key-2026")

TEST_USERS = [
    {
        "username": "andre.nascimento",
        "email": "andre.nascimento@darueira.local",
        "password": "Darueira@2026!",
        "tenant": "darueira-corp",
        "department": "darueira-corp",
        "expected_domain": "darueira.local"
    },
    {
        "username": "alice.developer",
        "email": "alice.developer@darueira.local",
        "password": "Darueira@2026!",
        "tenant": "acme",
        "department": "acme",
        "expected_domain": "darueira.local"
    },
    {
        "username": "bob.engineer",
        "email": "bob.engineer@darueira.local",
        "password": "Darueira@2026!",
        "tenant": "acme",
        "department": "acme",
        "expected_domain": "darueira.local"
    },
    {
        "username": "carol.contractor",
        "email": "carol.contractor@globex.local",
        "password": "Darueira@2026!",
        "tenant": "globex",
        "department": "globex",
        "expected_domain": "globex.local"
    }
]


def acquire_keycloak_token(username, password, retries=3):
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": username,
        "password": password,
        "grant_type": "password"
    }).encode("utf-8")
    
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                KEYCLOAK_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["access_token"]
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    raise last_err


def test_jmap_user(user_info, jwt_token):
    session_url = f"http://{STALWART_HTTP_HOST}/jmap/session"
    s_req = urllib.request.Request(session_url, headers={"Authorization": f"Bearer {jwt_token}"})
    with urllib.request.urlopen(s_req, timeout=10) as resp:
        session = json.loads(resp.read().decode("utf-8"))

    auth_user = session.get("username")
    assert auth_user == user_info["email"], f"Expected JMAP user {user_info['email']}, got {auth_user}"
    
    primary_acc = session.get("primaryAccounts", {}).get("urn:ietf:params:jmap:mail")
    assert primary_acc, f"No primary mail account ID for {user_info['username']}"

    # Query mailboxes
    api_url = f"http://{STALWART_HTTP_HOST}/jmap/"
    payload = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [["Mailbox/get", {"accountId": primary_acc, "ids": None}, "c1"]]
    }
    j_req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt_token}"}
    )
    with urllib.request.urlopen(j_req, timeout=10) as resp:
        j_resp = json.loads(resp.read().decode("utf-8"))

    mailboxes = j_resp["methodResponses"][0][1].get("list", [])
    box_roles = {m.get("role") for m in mailboxes if m.get("role")}
    required_roles = {"inbox", "sent", "drafts", "trash", "junk"}
    assert required_roles.issubset(box_roles), f"Missing standard mailboxes: {required_roles - box_roles}"
    return primary_acc, [m.get("name") for m in mailboxes]


def test_imap_xoauth2(user_info, jwt_token):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    imap = imaplib.IMAP4_SSL(STALWART_IMAP_HOST, 993, ssl_context=ctx)
    user_email = user_info["email"]
    auth_str = f"user={user_email}\x01auth=Bearer {jwt_token}\x01\x01"

    res = imap.authenticate("XOAUTH2", lambda x: auth_str)
    assert res[0] == "OK", f"IMAP XOAUTH2 authentication failed for {user_email}: {res}"

    typ, folders = imap.list()
    assert typ == "OK", f"IMAP list folders failed: {folders}"

    typ, cnt = imap.select("INBOX")
    assert typ == "OK", f"IMAP select INBOX failed: {cnt}"
    imap.logout()


def test_smtp_and_jmap_flow(sender_info, recipient_info, recipient_token, recipient_acc_id):
    subject = f"IAM Test Delivery at {int(time.time())}"
    body = "Verifying automated corporate mail delivery with Keycloak OIDC authentication."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_info["email"]
    msg["To"] = recipient_info["email"]

    # 1. Send via SMTP port 25
    smtp = smtplib.SMTP(STALWART_SMTP_HOST, 25)
    smtp.ehlo()
    smtp.sendmail(sender_info["email"], [recipient_info["email"]], msg.as_string())
    smtp.quit()

    # 2. Poll via JMAP with recipient token (MTA queue delivery)
    api_url = f"http://{STALWART_HTTP_HOST}/jmap/"
    payload = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            ["Email/query", {"accountId": recipient_acc_id, "filter": {"subject": subject}}, "c1"],
            ["Email/get", {"accountId": recipient_acc_id, "#ids": {"resultOf": "c1", "name": "Email/query", "path": "/ids"}}, "c2"]
        ]
    }
    
    for attempt in range(1, 6):
        time.sleep(1.0)
        j_req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {recipient_token}"}
        )
        with urllib.request.urlopen(j_req, timeout=10) as resp:
            j_resp = json.loads(resp.read().decode("utf-8"))

        emails = j_resp["methodResponses"][1][1].get("list", [])
        if emails:
            received_email = emails[0]
            assert received_email.get("subject") == subject, f"Subject mismatch: {received_email.get('subject')}"
            return subject

    raise AssertionError(f"Sent email '{subject}' was not found in recipient inbox via JMAP after polling")


def main():
    print("==================================================================")
    print("  Phase 02: Stalwart Mail & IAM Federation Validation Suite       ")
    print("==================================================================")

    tokens = {}
    account_ids = {}

    # Test 1: Keycloak OIDC Token Issuance & Stalwart JMAP Session Discovery
    print("\n[1/4] Testing Keycloak OIDC Authentication & Stalwart JMAP Mailbox Discovery...")
    for user in TEST_USERS:
        u_name = user["username"]
        u_email = user["email"]
        print(f"  --> Authenticating {u_email} via Keycloak Central IdP...")
        token = acquire_keycloak_token(u_name, user["password"])
        tokens[u_name] = token
        print(f"      [✓] Acquired OIDC Bearer Token for {u_name}")

        print(f"  --> Validating Stalwart JMAP session for {u_email}...")
        acc_id, mailboxes = test_jmap_user(user, token)
        account_ids[u_name] = acc_id
        print(f"      [✓] JMAP Authenticated as {u_email} (Acc ID: {acc_id})")
        print(f"      [✓] Mailboxes available: {mailboxes}")

    # Test 2: IMAP4rev2 XOAUTH2 Verification
    print("\n[2/4] Testing IMAP4rev2 XOAUTH2 Authentication with Keycloak Bearer Tokens...")
    for user in TEST_USERS:
        u_email = user["email"]
        u_token = tokens[user["username"]]
        print(f"  --> Connecting to IMAPS :993 and validating XOAUTH2 for {u_email}...")
        test_imap_xoauth2(user, u_token)
        print(f"      [✓] IMAP XOAUTH2 authenticated & INBOX selected for {u_email}")

    # Test 3: Cross-Tenant SMTP Mail Delivery & Real-Time JMAP Retrieval
    print("\n[3/4] Testing Cross-Tenant SMTP Mail Delivery & Real-Time JMAP Retrieval...")
    sender = TEST_USERS[1]       # alice.developer (Tenant: acme)
    recipient = TEST_USERS[0]    # andre.nascimento (Tenant: darueira-corp)
    recip_token = tokens[recipient["username"]]
    recip_acc = account_ids[recipient["username"]]

    print(f"  --> Dispatching SMTP email from {sender['email']} to {recipient['email']}...")
    subj = test_smtp_and_jmap_flow(sender, recipient, recip_token, recip_acc)
    print(f"      [✓] Email '{subj}' delivered via SMTP and verified in JMAP Inbox!")

    # Test 4: Partner Tenant SMTP Delivery & JMAP Retrieval
    print("\n[4/4] Testing Partner Tenant SMTP Delivery (Globex -> Acme)...")
    sender_p = TEST_USERS[3]     # carol.contractor (Tenant: globex, globex.local)
    recipient_p = TEST_USERS[2]  # bob.engineer (Tenant: acme, darueira.local)
    recip_p_token = tokens[recipient_p["username"]]
    recip_p_acc = account_ids[recipient_p["username"]]

    print(f"  --> Dispatching SMTP email from {sender_p['email']} to {recipient_p['email']}...")
    subj_p = test_smtp_and_jmap_flow(sender_p, recipient_p, recip_p_token, recip_p_acc)
    print(f"      [✓] Email '{subj_p}' delivered via SMTP and verified in JMAP Inbox!")

    print("\n==================================================================")
    print("  [✓✓✓] ALL PHASE 02 STALWART IAM VALIDATION TESTS PASSED!       ")
    print("==================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[✗] Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
