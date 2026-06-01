-- GPFC #91: Register options FVG/CHoCH setup in dashboard control table.
INSERT INTO setup_config (setup_type, enabled)
VALUES ('FVG_CHOCH', true)
ON CONFLICT (setup_type) DO NOTHING;
