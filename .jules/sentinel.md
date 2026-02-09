## 2025-01-09 - Azure Table Storage Injection
**Vulnerability:** Found a potential OData injection in Azure Table Storage queries where `project_key` and `branch` were directly concatenated into the filter string.
**Learning:** Developers may assume NoSQL databases like Azure Table Storage are immune to injection, but string concatenation for queries is always risky.
**Prevention:** Use parameterized queries (`parameters` argument in `query_entities`) instead of string interpolation.

## 2026-02-10 - Azure Table Storage PartitionKey Collision
**Vulnerability:** Found a logic vulnerability where different `project_key` and `branch` combinations (e.g., `my_project` + `main` vs. `my` + `project_main`) resulted in the same `PartitionKey`, leading to data mixing and potential data loss during deletion.
**Learning:** Concatenating strings to form a key without a unique separator or encoding can lead to collisions. Relying solely on a derived key for security/isolation is dangerous.
**Prevention:** Always filter by the original unique properties (`ProjectKey` and `Branch`) in addition to the derived key (`PartitionKey`) to ensure operations affect only the intended data.
