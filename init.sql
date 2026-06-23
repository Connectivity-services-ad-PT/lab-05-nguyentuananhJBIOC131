CREATE TABLE IF NOT EXISTS device_registry (
    device_id VARCHAR(100) PRIMARY KEY,
    device_type VARCHAR(100),
    location VARCHAR(100),
    room VARCHAR(50),
    status VARCHAR(50)
);

-- Nạp dữ liệu từ file CSV được mount vào container
COPY device_registry(device_id, device_type, location, room, status)
FROM '/docker-entrypoint-initdb.d/device_registry.csv'
DELIMITER ',' CSV HEADER;