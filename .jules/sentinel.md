## 2025-01-09 - Azure Table Storage Injection
**Vulnerability:** Found a potential OData injection in Azure Table Storage queries where `project_key` and `branch` were directly concatenated into the filter string.
**Learning:** Developers may assume NoSQL databases like Azure Table Storage are immune to injection, but string concatenation for queries is always risky.
**Prevention:** Use parameterized queries (`parameters` argument in `query_entities`) instead of string interpolation.

## 2026-02-10 - Azure Table Storage PartitionKey Collision
**Vulnerability:** Found a logic vulnerability where different `project_key` and `branch` combinations (e.g., `my_project` + `main` vs. `my` + `project_main`) resulted in the same `PartitionKey`, leading to data mixing and potential data loss during deletion.
**Learning:** Concatenating strings to form a key without a unique separator or encoding can lead to collisions. Relying solely on a derived key for security/isolation is dangerous.
**Prevention:** Always filter by the original unique properties (`ProjectKey` and `Branch`) in addition to the derived key (`PartitionKey`) to ensure operations affect only the intended data.

## 2025-05-22 - Azure Table Storage PartitionKey Sanitization
**Vulnerability:** Application crashed when storing metrics for branches with names containing '/', because Azure Table Storage PartitionKey forbids '/', '\', '#', '?'.
**Learning:** Input validation must extend to storage keys. Even if the value is safe for query parameters, it might be invalid as a key component.
**Prevention:** Sanitize derived keys (PartitionKey, RowKey) by replacing invalid characters before use. Ensure collision handling (e.g. secondary filters) is in place if sanitization reduces entropy.

## 2026-02-11 - External API Request Timeouts
**Vulnerability:** The application made external API calls to SonarCloud without specifying a timeout, making it vulnerable to indefinite hangs if the service is unresponsive (DoS).
**Learning:** Python's `requests` library does not enforce a timeout by default. Relying on default behavior for external dependencies can introduce availability risks.
**Prevention:** Always specify a `timeout` parameter (e.g., `timeout=30`) when making network requests to prevent resource exhaustion and application freezes.

## 2026-03-01 - Azure Table Storage Full Table Scan (DoS)
**Vulnerability:** The `get_stored_projects` method listed all entities in the `SonarCloudMetrics` table without projection, leading to excessive data transfer and potential resource exhaustion (DoS) as the table grows.
**Learning:** Fetching full entities when only a specific property is needed is a common anti-pattern that degrades performance and availability.
**Prevention:** Use the `select` parameter in `list_entities` (e.g., `select='ProjectKey'`) to retrieve only the necessary fields, minimizing payload size and latency.

## 2026-03-01 - Azure Table Storage PartitionKey Length Validation
**Vulnerability:** The `_get_partition_key` method did not validate the length of the generated PartitionKey, allowing potentially unlimited input length which could cause API errors or other issues. Azure limits PartitionKey to 1 KiB.
**Learning:** Input validation must include length constraints imposed by the underlying storage system to prevent API failures and potential DoS vectors.
**Prevention:** Enforce length limits on derived keys before attempting storage operations (e.g., raise `ValueError` if `len(key) > 1024`).

## 2026-06-15 - Azure Table Storage Full Scan DoS Prevention
**Vulnerability:** `get_stored_projects` performed a full table scan of millions of metrics records to list unique projects, leading to potential DoS.
**Learning:** Even with projection (`select='ProjectKey'`), iterating over all entities in a large table is resource-intensive. NoSQL stores require explicit indexing strategies for unique value listing.
**Prevention:** Implemented a "Metadata Partition" (`METADATA_PROJECTS`) acting as a read-through cache. It stores a list of unique projects separately. A lazy migration (backfill) mechanism ensures existing data is indexed on first access.
