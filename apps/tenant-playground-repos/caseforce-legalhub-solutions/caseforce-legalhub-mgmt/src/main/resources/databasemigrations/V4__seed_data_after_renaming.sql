-- Seed a partner agency
INSERT INTO tb_partner_agency(id, ds_alias, ds_name, ds_email, en_status)
SELECT
    id,
    UPPER(REPLACE(TRIM(name), ' ', '-')) AS alias,
    name,
    email,
    status
FROM partner_agency;

-- Seed a user (password: TestPass123)
INSERT INTO tb_user (id,
                     ds_email,
                     ds_firstname,
                     ds_lastname,
                     ds_password,
                     is_enabled)
SELECT id,
       email,
       firstname,
       lastname,
       password,
       enabled
FROM user;

-- Give ROOT role
INSERT INTO tb_user_role (id,
                          ds_role,
                          user_id)
SELECT id,
       role,
       user_id
FROM user_role;

-- Create admin group with all permissions
INSERT INTO tb_permission_group (id,
                                 ds_name,
                                 js_permissions)
SELECT id,
       name,
       permissions
FROM permission_group;

-- Add user to group
INSERT INTO tb_user_group (id,
                           user_id,
                           group_id)
SELECT id,
       user_id,
       group_id
FROM user_group;