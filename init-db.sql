CREATE TABLE IF NOT EXISTS registration_prospects (
    prospect_id VARCHAR(50) PRIMARY KEY,
    student_name VARCHAR(255) NOT NULL,
    student_email VARCHAR(255) NOT NULL,
    target_program VARCHAR(255) NOT NULL,
    transcript_text TEXT,
    is_qualified BOOLEAN,
    alternative_program VARCHAR(255),
    offer_sent BOOLEAN DEFAULT FALSE,
    student_accepted BOOLEAN,
    registration_fee_paid BOOLEAN DEFAULT FALSE,
    student_id VARCHAR(50),
    sis_sync_completed BOOLEAN DEFAULT FALSE,
    current_status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    prospect_id VARCHAR(50) REFERENCES registration_prospects(prospect_id) ON DELETE CASCADE,
    log_message TEXT NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prospect_status ON registration_prospects(current_status);