import type {
  CatalogSyncExecutionStatus,
  CatalogSyncFreshness,
  CatalogSyncSource,
} from "@/types/catalog-sync";


export const CATALOG_SYNC_SOURCE_ORDER:
  readonly CatalogSyncSource[] = [
    "satcat",
    "celestrak",
    "space-track",
  ];

export const CATALOG_SYNC_SOURCE_LABELS:
  Record<CatalogSyncSource, string> = {
    satcat:
      "SATCAT",

    celestrak:
      "CelesTrak",

    "space-track":
      "Space-Track",
  };

export const CATALOG_SYNC_FRESHNESS_LABELS:
  Record<CatalogSyncFreshness, string> = {
    fresh:
      "Fresh",

    warning:
      "Delayed",

    stale:
      "Stale",

    unknown:
      "Not available",
  };

export const CATALOG_SYNC_STATUS_LABELS:
  Record<CatalogSyncExecutionStatus, string> = {
    running:
      "Syncing",

    success:
      "Success",

    error:
      "Failed",

    never_run:
      "Never run",
  };


export function formatCatalogSyncAge(
  ageSeconds: number | null,
) {
  if (
    ageSeconds === null
    || !Number.isFinite(
      ageSeconds
    )
  ) {
    return "Not available";
  }

  const seconds =
    Math.max(
      0,
      Math.floor(
        ageSeconds
      ),
    );

  if (seconds < 60) {
    return "Just now";
  }

  const minutes =
    Math.floor(
      seconds / 60
    );

  if (minutes < 60) {
    return `${minutes} min ago`;
  }

  const hours =
    Math.floor(
      minutes / 60
    );

  if (hours < 24) {
    const remainingMinutes =
      minutes % 60;

    return remainingMinutes > 0
      ? `${hours} h ${remainingMinutes} min ago`
      : `${hours} h ago`;
  }

  return `${Math.floor(hours / 24)} d ago`;
}


export function formatCatalogSyncTimestamp(
  value: string | null,
) {
  if (value === null) {
    return "Not available";
  }

  const timestamp =
    new Date(value);

  if (
    Number.isNaN(
      timestamp.getTime()
    )
  ) {
    return "Not available";
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle:
        "medium",

      timeStyle:
        "short",
    },
  ).format(
    timestamp
  );
}
