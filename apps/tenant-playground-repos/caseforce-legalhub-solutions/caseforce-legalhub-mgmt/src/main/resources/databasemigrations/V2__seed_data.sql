-- CaseForce LegalHub seeds, in the state the MySQL migrations V2, V4, V6 and V8 left them (ADR-0018).
-- Ids come from the identity columns; rows are linked by lookup, not by fixed ids.

-- Demo partner agency (alias derived as the old V4 did: upper case, spaces to dashes)
INSERT INTO tb_partner_agency (ds_alias, ds_name, ds_email, en_status)
VALUES ('DEMO-AGENCY', 'Demo Agency', 'agency@demo.de', 'ACTIVE');

-- Admin user (password: TestPass123) and the service user of the Fake Agency simulator
-- (fake-agency-client@legalhero.de / FakeAgencyPass2026!). The e-mail domain is a historical name; it is kept because the
-- simulator logs in with it.
INSERT INTO tb_user (ds_email, ds_firstname, ds_lastname, ds_password, is_enabled)
VALUES ('admin@legalhero.de', 'Admin', 'User', 'TestPass123', TRUE),
       ('fake-agency-client@legalhero.de', 'FakeAgency', 'ServiceClient', 'FakeAgencyPass2026!', TRUE);

INSERT INTO tb_user_role (ds_role, user_id)
SELECT 'ROOT', id FROM tb_user WHERE ds_email IN ('admin@legalhero.de', 'fake-agency-client@legalhero.de');

INSERT INTO tb_user_role (ds_role, user_id)
SELECT r.role, u.id
FROM tb_user u
CROSS JOIN (VALUES ('LEGAL_HERO'), ('CASEFORCE')) AS r(role)
WHERE u.ds_email = 'fake-agency-client@legalhero.de';

-- Admin group with every permission of the system
INSERT INTO tb_permission_group (ds_name, js_permissions)
VALUES ('Admin', '[
  "CASE_CREATE", "CASE_GET", "CASE_UPDATE", "CASE_LIST", "CASE_DELETE",
  "ACTION_CREATE", "ACTION_GET", "ACTION_UPDATE", "ACTION_LIST", "ACTION_DELETE",
  "USER_CREATE", "USER_GET", "USER_UPDATE", "USER_DELETE", "USER_LIST",
  "GROUP_CREATE", "GROUP_GET", "GROUP_UPDATE", "GROUP_DELETE", "GROUP_LIST",
  "GROUP_MEMBERSHIP_ADD", "GROUP_MEMBERSHIP_REMOVE", "GROUP_MEMBERSHIP_LIST",
  "AGENCY_CREATE", "AGENCY_GET", "AGENCY_LIST", "AGENCY_UPDATE",
  "WEBHOOK_CREATE", "WEBHOOK_GET", "WEBHOOK_UPDATE", "WEBHOOK_DELETE", "WEBHOOK_LIST",
  "BULK_OPERATION_CREATE", "BULK_OPERATION_GET"
]'::jsonb);

INSERT INTO tb_user_group (user_id, group_id)
SELECT u.id, g.id
FROM tb_user u
CROSS JOIN (SELECT id FROM tb_permission_group WHERE ds_name = 'Admin' ORDER BY id LIMIT 1) g
WHERE u.ds_email IN ('admin@legalhero.de', 'fake-agency-client@legalhero.de')
ON CONFLICT DO NOTHING;
