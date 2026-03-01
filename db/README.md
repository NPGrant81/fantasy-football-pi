# Database Directory Structure

This directory organizes all SQL-related files for the Fantasy Football Pi project. Follow this structure for maintainability and scalability:

- **migrations/**: Alembic migration scripts (timestamped, ordered)
- **schema/**: Base table definitions, grouped by domain (e.g., users, teams, matchups)
- **seeds/**: Initial data population scripts
- **functions/**: SQL functions and stored procedures
- **views/**: Materialized and standard views
- **triggers/**: Trigger definitions and trigger functions
- **extensions/**: Postgres extensions (uuid-ossp, pgcrypto, etc.)
- **utils/**: Shared SQL fragments, enums, helper scripts

**Naming conventions:**
- Use snake_case for all SQL files
- Prefix domain-specific files (e.g., users.create.sql, teams.seed.sql)
- Migrations must follow timestamp-based naming

Refer to docs/ARCHITECTURE.md for more details.