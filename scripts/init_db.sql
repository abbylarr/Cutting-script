-- Database seed / indexes (run AFTER alembic upgrade or init_db)
-- Tables are created by Alembic / SQLAlchemy models.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_user_id ON processing_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_tasks_status ON processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_film_projects_user_id ON film_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_film_projects_task_id ON film_projects(task_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
