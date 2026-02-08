## 2025-01-09 - Azure Table Storage Injection
**Vulnerability:** Found a potential OData injection in Azure Table Storage queries where `project_key` and `branch` were directly concatenated into the filter string.
**Learning:** Developers may assume NoSQL databases like Azure Table Storage are immune to injection, but string concatenation for queries is always risky.
**Prevention:** Use parameterized queries (`parameters` argument in `query_entities`) instead of string interpolation.
