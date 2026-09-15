import {
  OrbitalGlobe,
} from "@/components/globe/orbital-globe";

import {
  OrbitalViewControls,
} from "@/components/globe/orbital-view-controls";

import {
  OrbitalViewProvider,
} from "@/components/globe/orbital-view-context";

import {
  getLatestConjunctionRun,
  getVisualizationSnapshot,
} from "@/lib/api";


export default async function Home() {
  let run = null;
  let snapshot = null;


  try {
    [
      run,
      snapshot,
    ] = await Promise.all([
      getLatestConjunctionRun(),
      getVisualizationSnapshot(),
    ]);
  } catch {
    // Console remains available
    // if backend data is unavailable.
  }


  return (
    <OrbitalViewProvider>

      <main className="operationsConsole">

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


          <div className="headerStatus">

            <div className="statusItem">
              <span>
                OBJECTS
              </span>

              <strong>
                {
                  snapshot
                    ?.rendered_objects
                  ?? "—"
                }
              </strong>
            </div>


            <div className="statusItem">
              <span>
                CANDIDATES
              </span>

              <strong>
                {
                  run
                    ?.unique_candidates
                  ?? "—"
                }
              </strong>
            </div>


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


        <aside className="operationsSidebar">

          <div className="sidebarSection">
            <span className="sectionLabel">
              OBJECT SEARCH
            </span>

            <div className="searchField">
              <span>⌕</span>

              <input
                placeholder={
                  "Name or NORAD ID"
                }
              />
            </div>
          </div>


          <div className="sidebarSection">

            <div className="sectionHeader">
              <span className="sectionLabel">
                ORBITAL CATALOG
              </span>

              {run && (
                <span className="runId">
                  RUN #{run.id}
                </span>
              )}
            </div>


            <div className="compactMetric">
              <span>Elements</span>

              <strong>
                {
                  snapshot
                    ?.total_elements
                  ?? "—"
                }
              </strong>
            </div>


            <div className="compactMetric">
              <span>Rendered</span>

              <strong>
                {
                  snapshot
                    ?.rendered_objects
                  ?? "—"
                }
              </strong>
            </div>


            <div className="compactMetric">
              <span>Expired</span>

              <strong>
                {
                  snapshot
                    ?.expired_skips
                  ?? "—"
                }
              </strong>
            </div>


            <div className="compactMetric">
              <span>
                Propagation failures
              </span>

              <strong>
                {
                  snapshot
                    ?.propagation_failures
                  ?? "—"
                }
              </strong>
            </div>

          </div>


          <div className="sidebarSection">

            <span className="sectionLabel">
              CONJUNCTION SCREENING
            </span>


            <div className="compactMetric">
              <span>
                Raw candidates
              </span>

              <strong>
                {
                  run
                    ?.raw_candidates
                  ?? "—"
                }
              </strong>
            </div>


            <div className="compactMetric">
              <span>
                Refined pairs
              </span>

              <strong>
                {
                  run
                    ?.unique_candidates
                  ?? "—"
                }
              </strong>
            </div>


            <div className="compactMetric">
              <span>
                Conjunctions
              </span>

              <strong className="accentValue">
                {
                  run
                    ?.event_count
                  ?? "—"
                }
              </strong>
            </div>

          </div>


          <OrbitalViewControls />

        </aside>


        <section className="globeWorkspace">

          <OrbitalGlobe
            snapshot={
              snapshot
            }
          />

          <div className="viewportTitle">
            <span>
              GLOBAL ORBITAL VIEW
            </span>

            <strong>
              Earth / ITRS-ECEF
            </strong>
          </div>

        </section>


        <footer className="operationsTimeline">

          <button
            className="playButton"
            type="button"
          >
            ▶
          </button>


          <div className="timeReadout">
            <span>
              SNAPSHOT UTC
            </span>

            <strong>
              {
                snapshot
                  ? new Date(
                      snapshot.at
                    )
                    .toLocaleString()
                  : "No data"
              }
            </strong>
          </div>


          <div className="timelineTrack">
            <div className="timelineProgress" />
          </div>


          <div className="timeReadout right">
            <span>
              REFERENCE FRAME
            </span>

            <strong>
              {
                snapshot
                  ?.frame
                ?? "—"
              }
            </strong>
          </div>

        </footer>

      </main>

    </OrbitalViewProvider>
  );
}
