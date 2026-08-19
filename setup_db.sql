CREATE DATABASE IF NOT EXISTS pms_purchasing CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'pms_purchasing'@'localhost' IDENTIFIED BY 'pms_purchasing';
CREATE USER IF NOT EXISTS 'pms_purchasing'@'127.0.0.1' IDENTIFIED BY 'pms_purchasing';
GRANT ALL PRIVILEGES ON pms_purchasing.* TO 'pms_purchasing'@'localhost';
GRANT ALL PRIVILEGES ON pms_purchasing.* TO 'pms_purchasing'@'127.0.0.1';
FLUSH PRIVILEGES;