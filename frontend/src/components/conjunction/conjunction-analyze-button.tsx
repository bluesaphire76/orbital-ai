"use client";

import {
  useState,
} from "react";

import {
  useConjunctionFocus,
} from "@/components/conjunction/conjunction-focus-context";

import {
  useOrbitalPlayback,
} from "@/components/playback/orbital-playback-context";

import type {
  ConjunctionEvent,
} from "@/types/conjunction";


const TCA_WINDOW_MS =
  60
  * 60
  * 1000;


function sameTargets(
  left: number[],
  right: number[],
) {
  if (
    left.length
    !== right.length
  ) {
    return false;
  }


  const a =
    [...left].sort(
      (x, y) => x - y
    );

  const b =
    [...right].sort(
      (x, y) => x - y
    );


  return a.every(
    (
      value,
      index,
    ) =>
      value
      === b[index]
  );
}


export function ConjunctionAnalyzeButton({
  event,
}: {
  event:
    ConjunctionEvent;
}) {
  const [
    analyzing,
    setAnalyzing,
  ] = useState(false);


  const {
    loadForObjects,
    setIsPlaying,
  } = useOrbitalPlayback();


  const {
    setActiveEventId,
  } = useConjunctionFocus();


  async function analyze() {
    if (analyzing) {
      return;
    }


    const tca =
      new Date(
        event.tca
      );


    if (
      Number.isNaN(
        tca.getTime()
      )
    ) {
      return;
    }


    const targets = [
      event.primary_object_id,
      event.secondary_object_id,
    ];


    const start =
      new Date(
        tca.getTime()
        - TCA_WINDOW_MS
      );

    const end =
      new Date(
        tca.getTime()
        + TCA_WINDOW_MS
      );


    setAnalyzing(
      true
    );

    setIsPlaying(
      false
    );

    setActiveEventId(
      null
    );


    let finishMaterialization:
      (
        result: boolean
      ) => void =
        () => undefined;


    const materialized =
      new Promise<boolean>(
        resolve => {
          let completed =
            false;


          function finish(
            result: boolean,
          ) {
            if (completed) {
              return;
            }


            completed =
              true;


            window.clearTimeout(
              timeout
            );


            window.removeEventListener(
              "orbitalai:playback-materialized",
              handleMaterialized,
            );


            resolve(
              result
            );
          }


          finishMaterialization =
            finish;


          function handleMaterialized(
            materializedEvent:
              Event,
          ) {
            const customEvent =
              materializedEvent as CustomEvent<{
                objectIds:
                  number[];
              }>;


            const objectIds =
              customEvent.detail
                ?.objectIds
              ?? [];


            if (
              sameTargets(
                objectIds,
                targets,
              )
            ) {
              finish(
                true
              );
            }
          }


          const timeout =
            window.setTimeout(
              () => {
                finish(
                  false
                );
              },
              5000,
            );


          window.addEventListener(
            "orbitalai:playback-materialized",
            handleMaterialized,
          );
        }
      );


    try {
      /*
       * First load the authoritative
       * TCA-centered playback.
       *
       * This may contain objects absent
       * from the current-time snapshot.
       */
      const loaded =
        await loadForObjects(
          targets,
          false,
          {
            start:
              start
                .toISOString(),

            end:
              end
                .toISOString(),

            seekTo:
              tca
                .toISOString(),

            elementIds: [
              event
                .primary_element_id,

              event
                .secondary_element_id,
            ],
          },
        );


      if (!loaded) {
        finishMaterialization(
          false
        );

        return;
      }


      /*
       * Wait until OrbitalGlobe has
       * materialized all playback
       * entities before selecting them.
       */
      const ready =
        await materialized;


      if (!ready) {
        return;
      }


      window.dispatchEvent(
        new CustomEvent(
          "orbitalai:select-conjunction-pair",
          {
            detail: {
              primaryObjectId:
                event
                  .primary_object_id,

              secondaryObjectId:
                event
                  .secondary_object_id,
            },
          },
        ),
      );


      /*
       * Activating the event triggers the
       * existing TCA pair camera framing
       * and conjunction visualization.
       */
      setActiveEventId(
        event.id
      );

    } finally {
      setAnalyzing(
        false
      );
    }
  }


  return (
    <button
      className="conjunctionAnalyzeButton"
      disabled={
        analyzing
      }
      onClick={
        () => {
          void analyze();
        }
      }
      type="button"
    >
      {
        analyzing
          ? "LOADING..."
          : "ANALYZE"
      }
    </button>
  );
}
