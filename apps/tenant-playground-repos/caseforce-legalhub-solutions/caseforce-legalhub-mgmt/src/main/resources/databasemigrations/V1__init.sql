CREATE TABLE partner_agency(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    email        VARCHAR(255),
    status       VARCHAR(50)  NOT NULL DEFAULT 'ACTIVE',
    date_created TIMESTAMP             DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMP             DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    date_deleted TIMESTAMP    NULL
);

CREATE TABLE user(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    email        VARCHAR(255) NOT NULL UNIQUE,
    firstname    VARCHAR(255),
    lastname     VARCHAR(255),
    password     VARCHAR(255),
    enabled      BOOLEAN   DEFAULT TRUE,
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    date_deleted TIMESTAMP    NULL
);

CREATE TABLE user_role(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    role         VARCHAR(50) NOT NULL,
    user_id      BIGINT      NOT NULL,
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE permission_group(
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    permissions  JSON,
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE user_group(
    id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id  BIGINT NOT NULL,
    group_id BIGINT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (group_id) REFERENCES permission_group (id)
);

CREATE TABLE legal_case(
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    case_number       VARCHAR(50),
    legal_field       VARCHAR(50),
    status            VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    summary           TEXT,
    lawyer_id         BIGINT,
    assignee_id       BIGINT,
    partner_agency_id BIGINT,
    date_created      TIMESTAMP            DEFAULT CURRENT_TIMESTAMP,
    date_updated      TIMESTAMP            DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    date_deleted      TIMESTAMP   NULL,
    FOREIGN KEY (lawyer_id) REFERENCES user (id),
    FOREIGN KEY (assignee_id) REFERENCES user (id),
    FOREIGN KEY (partner_agency_id) REFERENCES partner_agency (id)
);

CREATE TABLE action(
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    legal_case_id BIGINT       NOT NULL,
    name          VARCHAR(255) NOT NULL,
    is_task       BOOLEAN               DEFAULT FALSE,
    status        VARCHAR(50)  NOT NULL DEFAULT 'OPEN',
    assignee_id   BIGINT,
    created_by_id BIGINT,
    due_date      DATE,
    notes         TEXT,
    date_created  TIMESTAMP             DEFAULT CURRENT_TIMESTAMP,
    date_updated  TIMESTAMP             DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    date_deleted  TIMESTAMP    NULL,
    FOREIGN KEY (legal_case_id) REFERENCES legal_case (id),
    FOREIGN KEY (assignee_id) REFERENCES user (id),
    FOREIGN KEY (created_by_id) REFERENCES user (id)
);
