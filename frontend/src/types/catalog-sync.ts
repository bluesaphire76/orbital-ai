export type CatalogSyncFreshness =
  | "fresh"
  | "warning"
  | "stale"
  | "unknown";

export type CatalogSyncExecutionStatus =
  | "never_run"
  | "running"
  | "success"
  | "error";

export type CatalogSyncSource =
  | "satcat"
  | "celestrak"
  | "space-track";

export interface CatalogSyncSourceStatus {
  running: boolean;
  status: CatalogSyncExecutionStatus;
  last_started_at: string | null;
  last_completed_at: string | null;
  last_success_at: string | null;
  last_duration_seconds: number | null;
  last_records: number | null;
  last_from_cache: boolean | null;
  consecutive_failures: number;
  next_retry_at: string | null;
  freshness: CatalogSyncFreshness;
  last_success_age_seconds: number | null;
  freshness_warning_seconds: number;
  freshness_stale_seconds: number;
}

export interface CatalogSyncStatus {
  updated_at: string | null;
  overall_freshness: CatalogSyncFreshness;
  sources: Record<
    CatalogSyncSource,
    CatalogSyncSourceStatus
  >;
}
