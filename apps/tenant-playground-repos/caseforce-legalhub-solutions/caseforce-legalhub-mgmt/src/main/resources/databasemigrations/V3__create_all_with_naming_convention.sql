CREATE TABLE tb_user (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_email        VARCHAR(255) NOT NULL UNIQUE,
    ds_firstname    VARCHAR(255),
    ds_lastname     VARCHAR(255),
    ds_password     VARCHAR(255),
    is_enabled      BOOLEAN   DEFAULT TRUE,
    ts_date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ts_date_deleted TIMESTAMP    NULL
) ENGINE = InnoDB;

CREATE TABLE tb_user_role (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_role         VARCHAR(50) NOT NULL,
    user_id         BIGINT      NOT NULL,
    ts_date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES tb_user (id)
) ENGINE = InnoDB;

CREATE TABLE tb_permission_group (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_name         VARCHAR(255) NOT NULL,
    js_permissions  JSON,
    ts_date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB;

CREATE TABLE tb_user_group (
    id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id  BIGINT NOT NULL,
    group_id BIGINT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES tb_user (id),
    FOREIGN KEY (group_id) REFERENCES tb_permission_group (id)
) ENGINE = InnoDB;

create unique index idx_user_group_unq
    on tb_user_group (user_id, group_id);

CREATE TABLE tb_partner_agency (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_alias        VARCHAR(20)  NOT NULL UNIQUE,
    ds_name         VARCHAR(255) NOT NULL,
    ds_email        VARCHAR(255),
    en_status       VARCHAR(50)  NOT NULL DEFAULT 'ACTIVE',
    ts_date_created TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ts_date_deleted TIMESTAMP    NULL
) ENGINE = InnoDB;


CREATE TABLE tb_legal_case (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_case_number    VARCHAR(50) NOT NULL UNIQUE,
    ds_legal_field    VARCHAR(50),
    en_status         VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    partner_agency_id BIGINT,
    lawyer_id         BIGINT,
    assignee_id       BIGINT,
    ts_date_created   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ts_date_deleted   TIMESTAMP   NULL,
    tx_summary        TEXT,

    FOREIGN KEY (lawyer_id) REFERENCES tb_user (id),
    FOREIGN KEY (assignee_id) REFERENCES tb_user (id),
    FOREIGN KEY (partner_agency_id) REFERENCES tb_partner_agency (id)
) ENGINE = InnoDB;

CREATE TABLE tb_action (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_name         VARCHAR(255) NOT NULL,
    is_task         BOOLEAN               DEFAULT FALSE,
    en_status       VARCHAR(50)  NOT NULL DEFAULT 'OPEN',
    dt_due_date     DATE,
    legal_case_id   BIGINT       NOT NULL,
    assignee_id     BIGINT,
    created_by_id   BIGINT,
    ts_date_created TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ts_date_deleted TIMESTAMP    NULL,
    tx_notes        TEXT,

    FOREIGN KEY (legal_case_id) REFERENCES tb_legal_case (id),
    FOREIGN KEY (assignee_id) REFERENCES tb_user (id),
    FOREIGN KEY (created_by_id) REFERENCES tb_user (id)
) ENGINE = InnoDB;


CREATE TABLE tb_webhook_subscription (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_target_url     VARCHAR(1024) NOT NULL,
    ds_secret         VARCHAR(255)  NOT NULL,
    en_status         VARCHAR(50)   NOT NULL DEFAULT 'ACTIVE',
    partner_agency_id BIGINT        NOT NULL,
    ts_date_created   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ts_date_deleted   TIMESTAMP     NULL,
    js_event_types    JSON          NOT NULL,

    FOREIGN KEY (partner_agency_id) REFERENCES tb_partner_agency (id) ON DELETE CASCADE,

    INDEX             idx_webhook_sub_agency (partner_agency_id, en_status),
    INDEX             idx_webhook_sub_deleted (ts_date_deleted)
) ENGINE = InnoDB;

CREATE TABLE tb_webhook_delivery (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_event_type           VARCHAR(50) NOT NULL,
    ds_entity_type          VARCHAR(50) NOT NULL,
    nr_entity_id            BIGINT      NOT NULL,
    en_status               VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    nr_response_status_code INT         NULL,
    nr_attempt_count        INT         NOT NULL DEFAULT 0,
    ts_last_attempt_at      TIMESTAMP   NULL,
    ts_date_created         TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated         TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    subscription_id         BIGINT      NOT NULL,
    tx_response_body        TEXT        NULL,
    tx_error_message        TEXT        NULL,
    js_payload              JSON        NOT NULL,

    FOREIGN KEY (subscription_id) REFERENCES tb_webhook_subscription (id) ON DELETE CASCADE,

    INDEX                   idx_webhook_deliv_sub (subscription_id),
    INDEX                   idx_webhook_deliv_status_attempt (en_status, ts_last_attempt_at),
    INDEX                   idx_webhook_deliv_created (ts_date_created)
) ENGINE = InnoDB;

CREATE TABLE tb_bulk_operation_job (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    ds_job_type        VARCHAR(50) NOT NULL DEFAULT 'CASE_REASSIGNMENT',
    en_status          VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    nr_total_count     INT         NOT NULL DEFAULT 0,
    nr_processed_count INT         NOT NULL DEFAULT 0,
    nr_success_count   INT         NOT NULL DEFAULT 0,
    nr_failed_count    INT         NOT NULL DEFAULT 0,
    ts_date_created    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    ts_date_updated    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    requested_by_id    BIGINT      NOT NULL,
    target_lawyer_id   BIGINT      NOT NULL,

    js_filter_criteria JSON        NOT NULL,
    js_error_summary   JSON        NULL,

    FOREIGN KEY (requested_by_id)  REFERENCES tb_user (id) ON DELETE CASCADE,
    FOREIGN KEY (target_lawyer_id) REFERENCES tb_user (id) ON DELETE CASCADE,

    INDEX              idx_bulk_job_status (en_status),
    INDEX              idx_bulk_job_user (requested_by_id)
) ENGINE = InnoDB;
