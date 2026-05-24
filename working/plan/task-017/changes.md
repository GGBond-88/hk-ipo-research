# Changes: Task-017

## Files
- [new] src/hk_ipo/storage/__init__.py
- [new] src/hk_ipo/storage/schema_sql.py
- [new] tests/test_storage_schema.py

## Summary
Implemented L6 SQLite schema with create_tables() function that creates all 6 tables (companies, uses, use_tags, company_tags, pipeline_runs, taxonomy_proposals) and 6 indices per spec section 4.2. Includes foreign-key cascading deletes, idempotent CREATE IF NOT EXISTS semantics, and comprehensive unit tests verifying table creation, column presence, indices, cascade behavior, and idempotency. Fixed a bug in the task-specified test_indices_created where r[1] was used instead of r[0] for a single-column SELECT query.
