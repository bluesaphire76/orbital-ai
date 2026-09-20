"use client";

import {
  useEffect,
  useState,
} from "react";

import {
  CATALOG_SYNC_FRESHNESS_LABELS,
  CATALOG_SYNC_SOURCE_LABELS,
  CATALOG_SYNC_SOURCE_ORDER,
  CATALOG_SYNC_STATUS_LABELS,
  formatCatalogSyncAge,
  formatCatalogSyncTimestamp,
} from "@/lib/catalog-sync";

import type {
  CatalogSyncStatus,
} from "@/types/catalog-sync";


const POLL_INTERVAL_MS =
  60_000;


export function CatalogSyncPanel() {
  const [status, setStatus] =
    useState<CatalogSyncStatus | null>(
      null
    );

  const [loading, setLoading] =
    useState(
      true
    );

  const [failed, setFailed] =
    useState(
      false
    );


  useEffect(
    () => {
      let active =
        true;

      let timer:
        ReturnType<typeof setTimeout>
        | null = null;

      let request:
        AbortController
        | null = null;


      const load =
        async () => {
          request =
            new AbortController();

          try {
            const response =
              await fetch(
                "/api/catalog/sync-status",
                {
                  cache:
                    "no-store",

                  signal:
                    request.signal,
                },
              );

            if (!response.ok) {
              throw new Error(
                `Catalog sync status request failed (${response.status})`
              );
            }

            const payload =
              (await response.json()) as CatalogSyncStatus;

            if (!active) {
              return;
            }

            setStatus(
              payload
            );

            setFailed(
              false
            );

          } catch (error) {
            if (
              !active
              || (
                error instanceof DOMException
                && error.name === "AbortError"
              )
            ) {
              return;
            }

            setStatus(
              null
            );

            setFailed(
              true
            );

          } finally {
            if (active) {
              setLoading(
                false
              );

              timer =
                setTimeout(
                  () => {
                    void load();
                  },
                  POLL_INTERVAL_MS,
                );
            }
          }
        };


      void load();


      return () => {
        active =
          false;

        if (timer !== null) {
          clearTimeout(
            timer
          );
        }

        request?.abort();
      };
    },
    [],
  );


  return (
    <section
      aria-busy={
        loading
      }
      aria-labelledby="catalog-sync-title"
      className="workspaceRailSection catalogSyncPanel"
    >
      <div className="workspaceSectionHeader catalogSyncHeader">
        <div>
          <span className="sectionLabel">
            HEALTH
          </span>

          <strong id="catalog-sync-title">
            Catalog Synchronization
          </strong>
        </div>

        {
          status
          && (
            <span
              className="catalogSyncBadge"
              data-freshness={
                status.overall_freshness
              }
            >
              {
                CATALOG_SYNC_FRESHNESS_LABELS[
                  status.overall_freshness
                ]
              }
            </span>
          )
        }
      </div>

      {
        loading
        && (
          <div
            aria-live="polite"
            className="catalogSyncMessage"
            role="status"
          >
            Loading synchronization status…
          </div>
        )
      }

      {
        !loading
        && failed
        && (
          <div
            className="catalogSyncMessage error"
            role="alert"
          >
            Catalog synchronization status is temporarily unavailable.
          </div>
        )
      }

      {
        !loading
        && status
        && (
          <div className="catalogSyncSources">
            {
              CATALOG_SYNC_SOURCE_ORDER.map(
                source => {
                  const row =
                    status.sources[
                      source
                    ];

                  return (
                    <article
                      className="catalogSyncSource"
                      key={
                        source
                      }
                    >
                      <div className="catalogSyncSourceHeader">
                        <strong>
                          {
                            CATALOG_SYNC_SOURCE_LABELS[
                              source
                            ]
                          }
                        </strong>

                        <span
                          className="catalogSyncBadge"
                          data-freshness={
                            row.freshness
                          }
                        >
                          {
                            CATALOG_SYNC_FRESHNESS_LABELS[
                              row.freshness
                            ]
                          }
                        </span>
                      </div>

                      <dl className="catalogSyncFacts">
                        <div>
                          <dt>
                            Last success
                          </dt>

                          <dd>
                            {
                              row.last_success_at
                                ? (
                                  <>
                                    <time dateTime={row.last_success_at}>
                                      {
                                        formatCatalogSyncTimestamp(
                                          row.last_success_at
                                        )
                                      }
                                    </time>

                                    <span>
                                      {
                                        formatCatalogSyncAge(
                                          row.last_success_age_seconds
                                        )
                                      }
                                    </span>
                                  </>
                                )
                                : "Not available"
                            }
                          </dd>
                        </div>

                        <div>
                          <dt>
                            Last sync
                          </dt>

                          <dd>
                            {
                              CATALOG_SYNC_STATUS_LABELS[
                                row.status
                              ]
                            }
                          </dd>
                        </div>

                        {
                          row.consecutive_failures > 0
                          && (
                            <div>
                              <dt>
                                Consecutive failures
                              </dt>

                              <dd>
                                {
                                  row.consecutive_failures
                                }
                              </dd>
                            </div>
                          )
                        }

                        {
                          row.next_retry_at
                          && (
                            <div>
                              <dt>
                                Next retry
                              </dt>

                              <dd>
                                <time dateTime={row.next_retry_at}>
                                  {
                                    formatCatalogSyncTimestamp(
                                      row.next_retry_at
                                    )
                                  }
                                </time>
                              </dd>
                            </div>
                          )
                        }
                      </dl>
                    </article>
                  );
                }
              )
            }
          </div>
        )
      }
    </section>
  );
}
