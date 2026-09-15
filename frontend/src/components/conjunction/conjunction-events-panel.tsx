"use client";

import {
  useOrbitalPlayback,
} from "@/components/playback/orbital-playback-context";

import {
  useConjunctionFocus,
} from "@/components/conjunction/conjunction-focus-context";

import type {
  ConjunctionEvent,
} from "@/types/conjunction";


function formatTca(
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

  return date
    .toISOString()
    .replace(
      "T",
      " "
    )
    .replace(
      ".000Z",
      "Z"
    );
}


export function ConjunctionEventsPanel({
  events,
}: {
  events:
    ConjunctionEvent[];
}) {
  const {
    playback,
    seekToTime,
    setIsPlaying,
  } = useOrbitalPlayback();

  const {
    activeEventId,
    setActiveEventId,
  } = useConjunctionFocus();


  function isInsidePlayback(
    event:
      ConjunctionEvent
  ) {
    if (!playback) {
      return false;
    }

    const tca =
      new Date(
        event.tca
      ).getTime();

    const start =
      new Date(
        playback.start
      ).getTime();

    const end =
      new Date(
        playback.end
      ).getTime();

    return (
      Number.isFinite(
        tca
      )
      && tca >= start
      && tca <= end
    );
  }


  if (
    events.length === 0
  ) {
    return (
      <div className="sidebarSection">

        <span className="sectionLabel">
          CONJUNCTION EVENTS
        </span>

        <div className="conjunctionEmpty">
          No events in latest
          screening run
        </div>

      </div>
    );
  }


  return (
    <div className="sidebarSection">

      <span className="sectionLabel">
        CONJUNCTION EVENTS
      </span>


      <div className="conjunctionEventList">

        {events.map(
          event => {
            const available =
              isInsidePlayback(
                event
              );

            return (
              <article
                className={
                  activeEventId
                  === event.id
                    ? "conjunctionEventCard active"
                    : "conjunctionEventCard"
                }
                key={
                  event.id
                }
              >

                <div className="conjunctionEventPair">
                  <strong>
                    {
                      event
                        .primary_name
                    }
                  </strong>

                  <span>
                    ×
                  </span>

                  <strong>
                    {
                      event
                        .secondary_name
                    }
                  </strong>
                </div>


                <div className="conjunctionEventMetric">
                  <span>
                    TCA
                  </span>

                  <strong>
                    {
                      formatTca(
                        event.tca
                      )
                    }
                  </strong>
                </div>


                <div className="conjunctionEventMetric">
                  <span>
                    MISS DISTANCE
                  </span>

                  <strong>
                    {
                      event
                        .miss_distance_km
                        .toFixed(
                          3
                        )
                    } km
                  </strong>
                </div>


                <div className="conjunctionEventMetric">
                  <span>
                    RELATIVE VELOCITY
                  </span>

                  <strong>
                    {
                      event
                        .relative_velocity_km_s
                        .toFixed(
                          3
                        )
                    } km/s
                  </strong>
                </div>


                <button
                  disabled={
                    !available
                  }
                  onClick={() => {
                    setIsPlaying(
                      false
                    );

                    setActiveEventId(
                      event.id
                    );

                    seekToTime(
                      event.tca
                    );
                  }}
                  type="button"
                >
                  {
                    available
                      ? "FOCUS TCA"
                      : "OUTSIDE PLAYBACK"
                  }
                </button>

              </article>
            );
          }
        )}

      </div>

    </div>
  );
}
