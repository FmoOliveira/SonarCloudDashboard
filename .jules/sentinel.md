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

## 2026-03-02 - Azure Table Storage Metadata Partition (DoS Prevention)
**Vulnerability:** The `get_stored_projects` method performed a full table scan (iterating all entities) even with projection, which scales linearly with data size and can lead to timeouts or resource exhaustion.
**Learning:** Projection (`select`) reduces payload size but not the scan cost on the server side for finding entities. Primary keys (PartitionKey) must be used for efficient retrieval.
**Prevention:** Implement a "Metadata Partition" pattern: maintain a separate partition that indexes unique entities (projects), allowing O(1) or O(N_projects) retrieval instead of O(N_total_records).

## 2026-03-03 - Azure Table Storage Metadata RowKey Collision
**Vulnerability:** The `METADATA_PROJECTS` partition used a sanitized `ProjectKey` as its `RowKey`. Because sanitization (replacing `/` with `_`) is lossy, different project keys (e.g. `project/A` and `project_A`) resulted in the same `RowKey`, causing one to overwrite the other in the index.
**Learning:** When using derived keys for uniqueness in a NoSQL store, ensure the derivation function is collision-resistant. Simple string replacement reduces entropy and causes collisions.
**Prevention:** Use a cryptographic hash (SHA-256) of the original value as the key when the value contains invalid characters, ensuring both uniqueness and compliance with storage constraints.

## 2026-03-04 - Azure Table Storage Resource Exhaustion (DoS)
**Vulnerability:** The application retrieved an unlimited number of records in `retrieve_metrics_data` and `get_stored_projects`, potentially causing memory exhaustion (OOM) if the dataset grows large.
**Learning:** Assuming data volume will remain small is a dangerous assumption. Always enforce upper bounds on data retrieval operations to protect application stability.
**Prevention:** Implement a hard limit (e.g., `MAX_RETRIEVAL_LIMIT`) on loops processing external data or database cursors, and warn/fail gracefully when the limit is reached.
## 2026-03-04 - Azure Table Storage Excessive Data Exposure
**Vulnerability:** The `retrieve_metrics_data` method retrieved all columns (properties) from Azure Table Storage entities, potentially exposing sensitive data if the schema changes or if malicious data is injected.
**Learning:** Applications should follow the Principle of Least Privilege and Data Minimization by requesting only the data they need.
**Prevention:** Use the `select` parameter in Azure Table Storage queries to explicitly whitelist the required columns.
