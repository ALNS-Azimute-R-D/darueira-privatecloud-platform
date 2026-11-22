-- Update Admin permission group with all available permissions in the system
UPDATE tb_permission_group
SET js_permissions = '[
  "CASE_CREATE",
  "CASE_GET",
  "CASE_UPDATE",
  "CASE_LIST",
  "CASE_DELETE",
  "ACTION_CREATE",
  "ACTION_GET",
  "ACTION_UPDATE",
  "ACTION_LIST",
  "ACTION_DELETE",
  "USER_CREATE",
  "USER_GET",
  "USER_UPDATE",
  "USER_DELETE",
  "USER_LIST",
  "GROUP_CREATE",
  "GROUP_GET",
  "GROUP_UPDATE",
  "GROUP_DELETE",
  "GROUP_LIST",
  "GROUP_MEMBERSHIP_ADD",
  "GROUP_MEMBERSHIP_REMOVE",
  "GROUP_MEMBERSHIP_LIST",
  "AGENCY_CREATE",
  "AGENCY_GET",
  "AGENCY_LIST",
  "AGENCY_UPDATE",
  "WEBHOOK_CREATE",
  "WEBHOOK_GET",
  "WEBHOOK_UPDATE",
  "WEBHOOK_DELETE",
  "WEBHOOK_LIST",
  "BULK_OPERATION_CREATE",
  "BULK_OPERATION_GET"
]'
WHERE ds_name = 'Admin';

-- Ensure fake-agency-client is associated with the Admin group
INSERT IGNORE INTO tb_user_group (user_id, group_id)
SELECT u.id, g.id
FROM tb_user u
CROSS JOIN (SELECT id FROM tb_permission_group WHERE ds_name = 'Admin' LIMIT 1) g
WHERE u.ds_email = 'fake-agency-client@legalhero.de';

-- Ensure admin@legalhero.de is associated with the Admin group
INSERT IGNORE INTO tb_user_group (user_id, group_id)
SELECT u.id, g.id
FROM tb_user u
CROSS JOIN (SELECT id FROM tb_permission_group WHERE ds_name = 'Admin' LIMIT 1) g
WHERE u.ds_email = 'admin@legalhero.de';
