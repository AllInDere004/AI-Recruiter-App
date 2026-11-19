# Production-like migration rehearsal

Credential-safe verification on an isolated child of production. Production was not modified.

```json
{
  "branch": "production-migration-rehearsal-20261110",
  "branch_id": "br-lucky-moon-azq5607n",
  "parent_branch_id": "br-summer-bread-az2p9coe",
  "parent_lsn": "0/1F0FC98",
  "parent_timestamp": "2026-11-10T11:37:35Z",
  "expires_at": "2026-11-17T18:00:00Z",
  "production_modified": false,
  "status": "passed",
  "select_1": true,
  "direct_tls_connection": true,
  "production_endpoint_excluded": true,
  "original_table_count": 10,
  "new_table_count": 21,
  "original_row_counts_preserved": true,
  "original_metadata_preserved": true,
  "new_tables_empty": true,
  "ownership_foreign_keys_verified": 21,
  "new_table_indexes_verified": 74,
  "migration_history_unchanged": true,
  "recorded_migrations": [
    "001_recruiter.sql"
  ],
  "migration_seconds": {
    "002_career_intelligence.sql": 0.11,
    "003_smart_job_discovery.sql": 0.161,
    "004_advanced_features.sql": 0.161
  }
}
```
