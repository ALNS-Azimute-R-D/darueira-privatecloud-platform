-- Seed specific service user for Fake Agency simulator integration
-- User: fake-agency-client@legalhero.de / FakeAgencyPass2026!
INSERT INTO tb_user (ds_email, ds_firstname, ds_lastname, ds_password, is_enabled)
VALUES ('fake-agency-client@legalhero.de', 'FakeAgency', 'ServiceClient', 'FakeAgencyPass2026!', true);

-- Assign roles (ROOT, LEGAL_HERO, CASEFORCE)
INSERT INTO tb_user_role (ds_role, user_id)
SELECT 'ROOT', id FROM tb_user WHERE ds_email = 'fake-agency-client@legalhero.de';

INSERT INTO tb_user_role (ds_role, user_id)
SELECT 'LEGAL_HERO', id FROM tb_user WHERE ds_email = 'fake-agency-client@legalhero.de';

INSERT INTO tb_user_role (ds_role, user_id)
SELECT 'CASEFORCE', id FROM tb_user WHERE ds_email = 'fake-agency-client@legalhero.de';

-- Assign to Admin permission group
INSERT INTO tb_user_group (user_id, group_id)
SELECT u.id, g.id
FROM tb_user u
CROSS JOIN (SELECT id FROM tb_permission_group WHERE ds_name = 'Admin' LIMIT 1) g
WHERE u.ds_email = 'fake-agency-client@legalhero.de';
