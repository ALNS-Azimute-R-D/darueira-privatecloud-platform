#!/usr/bin/env python3
"""
Provisions the account that Alertmanager uses to SEND alert e-mails through Stalwart (backlog item 48).

Why: a message from a local domain that arrives unauthenticated on port 25 fails SPF and lands in Junk. With SMTP AUTH on the
submission port (465, implicit TLS: Stalwart has no listener on 587) the sender is authenticated and the alerts can reach the inbox.

How: Stalwart authenticates against the corporate directory (Authentik LDAP, dc=darueira,dc=local) and refuses local credentials
("Cannot set credentials for accounts in an external directory"). So the account is a user of the Authentik directory, created
the way scripts/bootstrap_authentik_directory.py creates users (Django ORM inside the authentik-server pod). Stalwart then
resolves it by LDAP.

What it does (idempotent):
  1. creates/updates the Authentik user `alertmanager` (mail alertmanager@darueira.local, no groups, no admin rights);
  2. generates the password IN MEMORY and sends it to the pod through stdin: it is never put on a command line, printed or
     written to a file or to Git; it is stored only in the Secret `alertmanager-smtp` (key `password`) in drr-corpshared-obs;
  3. proves the login (SMTP AUTH over implicit TLS on 465) without sending any message.

Usage: python3 scripts/provision_alertmanager_mail.py [--rotate]
  --rotate  new password (user and Secret); Alertmanager picks the Secret up on its next reload.
"""

import base64
import json
import secrets
import smtplib
import socket
import ssl
import string
import subprocess
import sys
import time

PLAT_NS = "drr-corpshared-plat"
OBS_NS = "drr-corpshared-obs"
SECRET = "alertmanager-smtp"
USERNAME = "alertmanager"
ADDRESS = "alertmanager@darueira.local"
PF_SMTP = 18465

# Runs inside authentik-server. `PASSWORD` and `ROTATE` are prepended by this script (stdin), see below.
DJANGO_SNIPPET = '''
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()
from authentik.core.models import User
user, created = User.objects.get_or_create(username="alertmanager", defaults={
    "name": "Alertmanager (alert sender)", "email": "alertmanager@darueira.local", "is_active": True,
    "attributes": {"type": "service-mail-sender", "managed-by": "scripts/provision_alertmanager_mail.py"}})
user.name, user.email, user.is_active = "Alertmanager (alert sender)", "alertmanager@darueira.local", True
if PASSWORD is not None:
    user.set_password(PASSWORD)
user.save()
print("CREATED" if created else "EXISTS", "password_set=%s" % (PASSWORD is not None))
'''


def kubectl(*args, stdin=None):
    return subprocess.run(["kubectl", *args], input=stdin, capture_output=True, text=True, check=True).stdout


def secret_exists():
    return subprocess.run(["kubectl", "-n", OBS_NS, "get", "secret", SECRET], capture_output=True).returncode == 0


def user_exists():
    code = "from authentik.core.models import User;print('YES' if User.objects.filter(username='alertmanager').exists() else 'NO')"
    out = kubectl("-n", PLAT_NS, "exec", "-i", "deploy/authentik-server", "-c", "server", "--", "python3", "-", stdin=(
        'import os, django\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")\ndjango.setup()\n' + code + "\n"))
    return out.strip().endswith("YES")


def main():
    rotate = "--rotate" in sys.argv
    password = None
    if rotate or not secret_exists() or not user_exists():
        password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    # The password travels in the stdin of the pod, as the first line of the script.
    payload = f"PASSWORD = {password!r}\n" + DJANGO_SNIPPET
    result = kubectl("-n", PLAT_NS, "exec", "-i", "deploy/authentik-server", "-c", "server", "--", "python3", "-", stdin=payload).strip()
    print(f"[+] Authentik user '{USERNAME}': {result.splitlines()[-1] if result else 'no output'}")

    if password is not None:
        subprocess.run(["kubectl", "-n", OBS_NS, "delete", "secret", SECRET, "--ignore-not-found"], capture_output=True, check=True)
        subprocess.run(["kubectl", "-n", OBS_NS, "create", "secret", "generic", SECRET, "--from-file=password=/dev/stdin"],
                       input=password, text=True, capture_output=True, check=True)
        kubectl("-n", OBS_NS, "label", "secret", SECRET, "app.kubernetes.io/name=alertmanager",
                "darueira.io/tier=enterprise-shared", "--overwrite")
        print(f"[+] Secret {SECRET} written")
    else:
        print(f"[=] user and Secret {SECRET} already exist (use --rotate to change the password)")

    # Login proof: AUTH over implicit TLS on 465. No message is sent.
    stored = base64.b64decode(kubectl("-n", OBS_NS, "get", "secret", SECRET, "-o", "jsonpath={.data.password}")).decode()
    pf = subprocess.Popen(["kubectl", "-n", PLAT_NS, "port-forward", "svc/stalwart-mail", f"{PF_SMTP}:465"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):   # wait for the port-forward
            try:
                socket.create_connection(("127.0.0.1", PF_SMTP), timeout=1).close()
                break
            except OSError:
                time.sleep(1)
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE   # lab: self-signed certificate
        last_error = None
        for login in (ADDRESS, USERNAME):
            for attempt in range(6):  # the LDAP outpost may need a moment to see a new user
                try:
                    smtp = smtplib.SMTP_SSL("127.0.0.1", PF_SMTP, timeout=15, context=ctx)
                    smtp.ehlo("alertmanager.drr-corpshared-obs")
                    smtp.login(login, stored)
                    smtp.quit()
                    print(f"[✓] SMTP AUTH works on 465 (implicit TLS) with login name '{login}'")
                    return
                except (smtplib.SMTPException, OSError) as exc:
                    last_error = f"{type(exc).__name__}: {str(exc)[:80]}"
                    time.sleep(3)
        sys.exit(f"SMTP AUTH failed for '{ADDRESS}' and '{USERNAME}': {last_error}")
    finally:
        pf.terminate()


if __name__ == "__main__":
    main()
