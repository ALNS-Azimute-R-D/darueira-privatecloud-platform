-- Seed a partner agency
INSERT INTO partner_agency (id, name, email, status) VALUES (1, 'Demo Agency', 'agency@demo.de', 'ACTIVE');

-- Seed a user (password: TestPass123)
INSERT INTO user (id, email, firstname, lastname, password, enabled) VALUES (1, 'admin@legalhero.de', 'Admin', 'User', 'TestPass123', true);

-- Give ROOT role
INSERT INTO user_role (id, role, user_id) VALUES (1, 'ROOT', 1);

-- Create admin group with all permissions
INSERT INTO permission_group (id, name, permissions) VALUES (1, 'Admin', '["CASE_CREATE","CASE_GET","CASE_UPDATE","CASE_LIST","CASE_DELETE","ACTION_CREATE","ACTION_GET","ACTION_UPDATE","ACTION_LIST","ACTION_DELETE","USER_GET","USER_LIST","AGENCY_GET","AGENCY_LIST","AGENCY_UPDATE"]');

-- Add user to group
INSERT INTO user_group (id, user_id, group_id) VALUES (1, 1, 1);
