-- Increase column length for partner agency alias and legal case fields to support full business slugs and identifiers
ALTER TABLE tb_partner_agency MODIFY COLUMN ds_alias VARCHAR(100) NOT NULL;
ALTER TABLE tb_legal_case MODIFY COLUMN ds_case_number VARCHAR(100) NOT NULL;
ALTER TABLE tb_legal_case MODIFY COLUMN ds_legal_field VARCHAR(100);
