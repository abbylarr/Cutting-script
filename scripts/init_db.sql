-- Database initialization script for filmlist

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_user_id ON processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_status ON processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_film_projects_user_id ON film_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_film_projects_task_id ON film_projects(task_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);

-- Create full-text search indexes
CREATE INDEX IF NOT EXISTS idx_film_projects_title_search ON film_projects USING gin(to_tsvector('russian', title));

-- Insert default data if needed
INSERT INTO users (email, password_hash, balance) 
VALUES ('admin@filmlist.com', '$2b$12$example_hash', 1000.00)
ON CONFLICT (email) DO NOTHING;