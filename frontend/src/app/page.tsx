import {
  OrbitalGlobe,
} from "@/components/globe/orbital-globe";


import {
  OrbitalCatalogSearch,
} from "@/components/globe/orbital-catalog-search";

import {
  OrbitalViewControls,
} from "@/components/globe/orbital-view-controls";

import {
  OrbitalViewProvider,
} from "@/components/globe/orbital-view-context";

import {
  OrbitalPlaybackProvider,
} from "@/components/playback/orbital-playback-context";

import {
  OrbitalPlaybackControls,
} from "@/components/playback/orbital-playback-controls";

import {
  getConjunctionEvents,
  getLatestConjunctionRun,
  getVisualizationSnapshot,
} from "@/lib/api";

import {
  ConjunctionFocusProvider,
} from "@/components/conjunction/conjunction-focus-context";

import {
  ConjunctionAnalyzeButton,
} from "@/components/conjunction/conjunction-analyze-button";

import type {
  ConjunctionEvent,
} from "@/types/conjunction";


function formatCompactTca(
  value: string,
) {
  const date =
    new Date(
      value
    );

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-GB",
    {
      timeZone:
        "Europe/Zurich",

      day:
        "2-digit",

      month:
        "short",

      hour:
        "2-digit",

      minute:
        "2-digit",

      second:
        "2-digit",

      hourCycle:
        "h23",

      timeZoneName:
        "short",
    },
  ).format(
    date
  );
}


export default async function Home() {
  let run = null;
  let snapshot = null;

  let events:
    ConjunctionEvent[] = [];


  try {
    [
      run,
      snapshot,
    ] = await Promise.all([
      getLatestConjunctionRun(),
      getVisualizationSnapshot(),
    ]);
  } catch {
    // The workspace remains available
    // if backend data is unavailable.
  }


  if (
    run
    && run.event_count > 0
  ) {
    try {
      events =
        await getConjunctionEvents(
          run.id
        );
    } catch {
      events = [];
    }
  }


  const now =
    new Date();


  const runWindowEnd =
    run
      ? new Date(
          run.window_end
        )
      : null;


  const screeningIsStale =
    runWindowEnd !== null
    && (
      Number.isNaN(
        runWindowEnd.getTime()
      )
      || runWindowEnd.getTime()
        < now.getTime()
    );


  const upcomingEvents =
    events
      .filter(
        event => {
          const tca =
            new Date(
              event.tca
            );


          return (
            !Number.isNaN(
              tca.getTime()
            )
            && tca.getTime()
              >= now.getTime()
          );
        }
      )
      .sort(
        (
          left,
          right,
        ) =>
          new Date(
            left.tca
          ).getTime()
          - new Date(
              right.tca
            ).getTime()
      );


  const priorityEvents =
    upcomingEvents.slice(
      0,
      5
    );


  return (
    <OrbitalViewProvider>
      <OrbitalPlaybackProvider
        autoload={false}
        initialSnapshotAt={
          snapshot?.at ?? null
        }
      >
        <ConjunctionFocusProvider>

          <main className="operationsConsole operationsWorkspaceV04">

            <header className="operationsHeader">

              <div className="productIdentity">
                <div className="orbitalLogo">
                  O
                </div>

                <div>
                  <strong>
                    OrbitalAI
                  </strong>

                  <span>
                    ORBITAL OPERATIONS
                  </span>
                </div>
              </div>


              <div className="workspaceHeaderCenter">
                <span>
                  GLOBAL CATALOG
                </span>

                <strong>
                  {
                    snapshot
                      ?.rendered_objects
                    ?? "—"
                  }{" "}
                  OBJECTS
                </strong>
              </div>


              <div className="headerStatus">

                <div className="statusItem">
                  <span>
                    EVENTS
                  </span>

                  <strong>
                    {
                      run
                        ?.event_count
                      ?? "—"
                    }
                  </strong>
                </div>


                <div
                  className={
                    snapshot
                      ? "systemState online"
                      : "systemState offline"
                  }
                >
                  <i />

                  {
                    snapshot
                      ? "SYSTEM ONLINE"
                      : "NO DATA"
                  }
                </div>

              </div>

            </header>


            <aside className="operationsSidebar operationsLeftRail">

              <OrbitalCatalogSearch />


              <section className="workspaceRailSection">
                <div className="workspaceSectionHeader">
                  <div>
                    <span className="sectionLabel">
                      CATALOG STATUS
                    </span>

                    <strong>
                      Global snapshot
                    </strong>
                  </div>

                  {
                    run
                    && (
                      <span className="runId">
                        RUN #{run.id}
                      </span>
                    )
                  }
                </div>


                <div className="workspaceMetricGrid">

                  <div className="workspaceMetric">
                    <span>
                      Elements
                    </span>

                    <strong>
                      {
                        snapshot
                          ?.total_elements
                        ?? "—"
                      }
                    </strong>
                  </div>


                  <div className="workspaceMetric">
                    <span>
                      Rendered
                    </span>

                    <strong>
                      {
                        snapshot
                          ?.rendered_objects
                        ?? "—"
                      }
                    </strong>
                  </div>


                  <div className="workspaceMetric">
                    <span>
                      Expired
                    </span>

                    <strong>
                      {
                        snapshot
                          ?.expired_skips
                        ?? "—"
                      }
                    </strong>
                  </div>


                  <div className="workspaceMetric">
                    <span>
                      Propagation errors
                    </span>

                    <strong
                      className={
                        snapshot
                        && snapshot
                          .propagation_failures
                        === 0
                          ? "healthyValue"
                          : ""
                      }
                    >
                      {
                        snapshot
                          ?.propagation_failures
                        ?? "—"
                      }
                    </strong>
                  </div>

                </div>
              </section>


              <section className="workspaceRailSection">
                <span className="sectionLabel">
                  SCREENING
                </span>

                <div className="workspaceMetricRow">
                  <span>
                    Candidates
                  </span>

                  <strong>
                    {
                      run
                        ?.unique_candidates
                      ?? "—"
                    }
                  </strong>
                </div>

                <div className="workspaceMetricRow">
                  <span>
                    Conjunction events
                  </span>

                  <strong className="accentValue">
                    {
                      run
                        ?.event_count
                      ?? "—"
                    }
                  </strong>
                </div>
              </section>


              <OrbitalViewControls />

            </aside>


            <section className="globeWorkspace">

              <OrbitalGlobe
                snapshot={
                  snapshot
                }
                conjunctionEvents={
                  events
                }
              />

              <div className="viewportTitle">
                <span>
                  LIVE CATALOG SNAPSHOT
                </span>

                <strong>
                  Earth / ITRS-ECEF
                </strong>
              </div>

            </section>


            <aside className="operationsContextRail">

              <section className="contextPanel">
                <span className="sectionLabel">
                  CONTEXT
                </span>

                <div className="contextEmptyState">
                  <strong>
                    Global view
                  </strong>

                  <p>
                    Select an orbital object
                    on the globe to inspect
                    and focus it.
                  </p>

                  <div className="contextFacts">
                    <span>
                      Labels are hidden by
                      default to keep the
                      globe readable.
                    </span>

                    <span>
                      Playback is loaded only
                      when an operation
                      requires it.
                    </span>
                  </div>
                </div>
              </section>


              <section className="contextPanel queuePanel">
                <div className="workspaceSectionHeader">
                  <div>
                    <span className="sectionLabel">
                      CONJUNCTION QUEUE
                    </span>

                    <strong>
                      Upcoming events
                    </strong>
                  </div>

                  <span className="queueCount">
                    {
                      screeningIsStale
                        ? "STALE"
                        : upcomingEvents.length
                    }
                  </span>
                </div>


                {
                  priorityEvents.length
                  === 0
                    ? (
                      <div className="contextEmptyState compact">
                        <p>
                          {
                            screeningIsStale
                              ? "Screening data is stale."
                              : "No upcoming conjunctions in the current screening window."
                          }
                        </p>
                      </div>
                    )
                    : (
                      <div className="compactEventQueue">
                        {
                          priorityEvents.map(
                            (
                              event,
                              index,
                            ) => (
                              <article
                                className="compactEventRow"
                                key={
                                  event.id
                                }
                              >
                                <div className="eventRank">
                                  {
                                    String(
                                      index + 1
                                    ).padStart(
                                      2,
                                      "0"
                                    )
                                  }
                                </div>

                                <div className="eventBody">
                                  <strong>
                                    {
                                      event
                                        .primary_name
                                    }
                                  </strong>

                                  <span className="eventPairSeparator">
                                    ×
                                  </span>

                                  <strong>
                                    {
                                      event
                                        .secondary_name
                                    }
                                  </strong>

                                  <div className="eventMeta">
                                    <span>
                                      {
                                        event
                                          .miss_distance_km
                                          .toFixed(
                                            3
                                          )
                                      }{" "}
                                      km
                                    </span>

                                    <span>
                                      {
                                        formatCompactTca(
                                          event.tca
                                        )
                                      }
                                    </span>
                                  </div>


                                  <ConjunctionAnalyzeButton
                                    event={
                                      event
                                    }
                                  />
                                </div>
                              </article>
                            )
                          )
                        }
                      </div>
                    )
                }


                {
                  upcomingEvents.length > 5
                  && (
                    <div className="queueFooter">
                      Showing 5 nearest of{" "}
                      {upcomingEvents.length}
                    </div>
                  )
                }
              </section>

            </aside>


            <footer className="operationsTimeline workspaceTimeline">
              <OrbitalPlaybackControls
                fallbackFrame={
                  snapshot
                    ?.frame
                  ?? "—"
                }
              />
            </footer>

          </main>

        </ConjunctionFocusProvider>
      </OrbitalPlaybackProvider>
    </OrbitalViewProvider>
  );
}
