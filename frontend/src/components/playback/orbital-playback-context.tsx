"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type {
  VisualizationPlayback,
} from "@/types/visualization";


export type PlaybackSpeed =
  1 | 10 | 100 | 1000;


interface SeekRequest {
  id: number;
  at: string;
}


interface PlaybackWindow {
  start: string;
  end: string;
  seekTo?: string;
  elementIds?: number[];
}


interface OrbitalPlaybackContextValue {
  playback:
    VisualizationPlayback | null;

  selectedObjectId:
    number | null;

  selectedObjectIds:
    number[];

  loadedObjectIds:
    number[];

  loadForObjects:
    (
      objectIds: number[],
      autoplay?: boolean,
      playbackWindow?: PlaybackWindow,
    ) => Promise<boolean>;

  loading: boolean;

  error:
    string | null;

  isPlaying: boolean;

  setIsPlaying:
    React.Dispatch<
      React.SetStateAction<boolean>
    >;

  speed:
    PlaybackSpeed;

  setSpeed:
    React.Dispatch<
      React.SetStateAction<
        PlaybackSpeed
      >
    >;

  currentTime:
    string | null;

  progress:
    number;

  seekRequest:
    SeekRequest | null;

  seekToTime:
    (
      isoTime: string
    ) => boolean;

  seekToFraction:
    (
      fraction: number
    ) => void;

  reportClockTime:
    (
      isoTime: string
    ) => void;

  reload:
    () => void;
}


const OrbitalPlaybackContext =
  createContext<
    OrbitalPlaybackContextValue
    | null
  >(
    null
  );


export function OrbitalPlaybackProvider({
  initialSnapshotAt,
  autoload = true,
  children,
}: {
  initialSnapshotAt:
    string | null;

  autoload?:
    boolean;

  children:
    React.ReactNode;
}) {
  const [
    playback,
    setPlayback,
  ] = useState<
    VisualizationPlayback | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(
    autoload
  );

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(null);

  const [
    isPlaying,
    setIsPlaying,
  ] = useState(false);

  const [
    speed,
    setSpeed,
  ] = useState<
    PlaybackSpeed
  >(1);

  const [
    currentTime,
    setCurrentTime,
  ] = useState<
    string | null
  >(
    initialSnapshotAt
  );

  const [
    seekRequest,
    setSeekRequest,
  ] = useState<
    SeekRequest | null
  >(null);

  const [
    reloadKey,
    setReloadKey,
  ] = useState(0);

  const [
    selectedObjectId,
    setSelectedObjectId,
  ] = useState<number | null>(
    null
  );


  const [
    selectedObjectIds,
    setSelectedObjectIds,
  ] = useState<number[]>(
    []
  );

  const [
    loadedObjectIds,
    setLoadedObjectIds,
  ] = useState<number[]>(
    []
  );

  const activeRequestRef =
    useRef<AbortController | null>(
      null
    );


  const loadedObjectIdsRef =
    useRef<number[]>(
      []
    );


  /*
   * Active target is visual focus only.
   * Changing focus inside an existing multi-selection
   * must not destroy the loaded multi-object playback.
   */
  useEffect(() => {
    function handleActiveObjectChange(
      event: Event,
    ) {
      const customEvent =
        event as CustomEvent<{
          objectId:
            number | null;
        }>;


      setSelectedObjectId(
        customEvent.detail
          ?.objectId
        ?? null
      );
    }


    window.addEventListener(
      "orbitalai:active-object-change",
      handleActiveObjectChange,
    );


    return () => {
      window.removeEventListener(
        "orbitalai:active-object-change",
        handleActiveObjectChange,
      );
    };

  }, []);


  /*
   * Complete selection defines the playback target set.
   * Any selection-set change invalidates the previous
   * targeted playback.
   */
  useEffect(() => {
    function handleSelectedObjectsChange(
      event: Event,
    ) {
      const customEvent =
        event as CustomEvent<{
          objectIds:
            number[];
        }>;


      const objectIds =
        Array.from(
          new Set(
            (
              customEvent.detail
                ?.objectIds
              ?? []
            ).filter(
              id =>
                Number.isInteger(id)
                && id > 0
            )
          )
        );


      setSelectedObjectIds(
        objectIds
      );


      const loadedTargets =
        loadedObjectIdsRef.current;


      const matchesLoadedPlayback =
        objectIds.length
          === loadedTargets.length
        && objectIds.every(
          objectId =>
            loadedTargets.includes(
              objectId
            )
        );


      /*
       * ANALYZE loads the authoritative
       * targeted playback first and then
       * asks the globe to select exactly
       * those objects.
       *
       * That selection must not invalidate
       * the playback that was just loaded.
       */
      if (
        matchesLoadedPlayback
        && objectIds.length > 0
      ) {
        return;
      }


      activeRequestRef.current
        ?.abort();

      activeRequestRef.current =
        null;

      loadedObjectIdsRef.current =
        [];


      setPlayback(
        null
      );

      setLoadedObjectIds(
        []
      );

      setIsPlaying(
        false
      );

      setLoading(
        false
      );

      setError(
        null
      );

      setCurrentTime(
        initialSnapshotAt
      );
    }


    window.addEventListener(
      "orbitalai:selected-objects-change",
      handleSelectedObjectsChange,
    );


    return () => {
      window.removeEventListener(
        "orbitalai:selected-objects-change",
        handleSelectedObjectsChange,
      );
    };

  }, [
    initialSnapshotAt,
  ]);


  useEffect(() => {
    if (!autoload) {
      return;
    }


    const controller =
      new AbortController();


    async function loadPlayback() {
      setLoading(
        true
      );

      setError(
        null
      );

      setIsPlaying(
        false
      );


      try {
        const startDate =
          initialSnapshotAt
            ? new Date(
                initialSnapshotAt
              )
            : new Date();


        if (
          Number.isNaN(
            startDate.getTime()
          )
        ) {
          throw new Error(
            "Invalid playback start time"
          );
        }


        const endDate =
          new Date(
            startDate.getTime()
            + (
              2
              * 60
              * 60
              * 1000
            )
          );


        const params =
          new URLSearchParams({
            start:
              startDate
                .toISOString(),

            end:
              endDate
                .toISOString(),

            step_seconds:
              "60",
          });


        const response =
          await fetch(
            `/api/visualization/playback?${params}`,
            {
              cache:
                "no-store",

              signal:
                controller.signal,
            },
          );


        if (!response.ok) {
          throw new Error(
            `Playback request failed (${response.status})`
          );
        }


        const data =
          (await response.json()) as VisualizationPlayback;


        if (
          controller
            .signal
            .aborted
        ) {
          return;
        }


        setPlayback(
          data
        );

        setCurrentTime(
          data.start
        );

        setSeekRequest(
          current => ({
            id:
              (
                current
                  ?.id
                ?? 0
              )
              + 1,

            at:
              data.start,
          })
        );

      } catch (loadError) {
        if (
          controller
            .signal
            .aborted
        ) {
          return;
        }


        setPlayback(
          null
        );

        setError(
          loadError
          instanceof Error
            ? loadError.message
            : "Playback loading failed"
        );

      } finally {
        if (
          !controller
            .signal
            .aborted
        ) {
          setLoading(
            false
          );
        }
      }
    }


    void loadPlayback();


    return () => {
      controller.abort();
    };

  }, [
    autoload,
    initialSnapshotAt,
    reloadKey,
  ]);


  const loadForObjects =
    useCallback(
      async (
        objectIds: number[],
        autoplay = false,
        playbackWindow?: PlaybackWindow,
      ) => {
        const targets =
          Array.from(
            new Set(
              objectIds
                .filter(
                  id =>
                    Number.isInteger(id)
                    && id > 0
                )
            )
          );


        if (
          targets.length === 0
        ) {
          setError(
            "No playback target selected"
          );

          return false;
        }


        if (
          targets.length > 16
        ) {
          setError(
            "Playback supports at most 16 targeted objects"
          );

          return false;
        }


        activeRequestRef.current
          ?.abort();


        const controller =
          new AbortController();


        activeRequestRef.current =
          controller;


        setLoading(
          true
        );

        setError(
          null
        );

        setIsPlaying(
          false
        );


        try {
          const startDate =
            playbackWindow
              ? new Date(
                  playbackWindow.start
                )
              : (
                  initialSnapshotAt
                    ? new Date(
                        initialSnapshotAt
                      )
                    : new Date()
                );


          if (
            Number.isNaN(
              startDate.getTime()
            )
          ) {
            throw new Error(
              "Invalid playback start time"
            );
          }


          const endDate =
            playbackWindow
              ? new Date(
                  playbackWindow.end
                )
              : new Date(
                  startDate.getTime()
                  + (
                    2
                    * 60
                    * 60
                    * 1000
                  )
                );


          if (
            Number.isNaN(
              endDate.getTime()
            )
            || endDate.getTime()
              <= startDate.getTime()
          ) {
            throw new Error(
              "Invalid playback end time"
            );
          }


          const params =
            new URLSearchParams({
              start:
                startDate
                  .toISOString(),

              end:
                endDate
                  .toISOString(),

              step_seconds:
                "60",
            });


          for (
            const objectId
            of targets
          ) {
            params.append(
              "object_id",
              String(
                objectId
              )
            );
          }


          for (
            const elementId
            of (
              playbackWindow
                ?.elementIds
              ?? []
            )
          ) {
            params.append(
              "element_id",
              String(
                elementId
              )
            );
          }


          const response =
            await fetch(
              `/api/visualization/playback?${params}`,
              {
                cache:
                  "no-store",

                signal:
                  controller.signal,
              },
            );


          if (!response.ok) {
            throw new Error(
              `Playback request failed (${response.status})`
            );
          }


          const data =
            (await response.json()) as VisualizationPlayback;


          if (
            controller.signal
              .aborted
          ) {
            return false;
          }


          const returnedIds =
            data.objects.map(
              object =>
                object.object_id
            );


          const missingTarget =
            targets.find(
              objectId =>
                !returnedIds.includes(
                  objectId
                )
            );


          if (
            missingTarget
            !== undefined
          ) {
            throw new Error(
              `Playback target ${missingTarget} was not returned`
            );
          }


          const seekTarget =
            playbackWindow
              ?.seekTo
            ?? data.start;


          const seekTime =
            new Date(
              seekTarget
            ).getTime();

          const playbackStart =
            new Date(
              data.start
            ).getTime();

          const playbackEnd =
            new Date(
              data.end
            ).getTime();


          if (
            !Number.isFinite(
              seekTime
            )
            || seekTime
              < playbackStart
            || seekTime
              > playbackEnd
          ) {
            throw new Error(
              "Playback seek target is outside loaded window"
            );
          }


          setPlayback(
            data
          );

          loadedObjectIdsRef.current =
            targets;


          setLoadedObjectIds(
            targets
          );

          setCurrentTime(
            seekTarget
          );

          setSeekRequest(
            current => ({
              id:
                (
                  current
                    ?.id
                  ?? 0
                )
                + 1,

              at:
                seekTarget,
            })
          );

          setIsPlaying(
            autoplay
          );


          return true;

        } catch (loadError) {
          if (
            controller.signal
              .aborted
          ) {
            return false;
          }


          setPlayback(
            null
          );

          loadedObjectIdsRef.current =
            [];


          setLoadedObjectIds(
            []
          );

          setIsPlaying(
            false
          );

          setError(
            loadError
            instanceof Error
              ? loadError.message
              : "Playback loading failed"
          );


          return false;

        } finally {
          if (
            activeRequestRef.current
            === controller
          ) {
            activeRequestRef.current =
              null;

            setLoading(
              false
            );
          }
        }
      },
      [
        initialSnapshotAt,
      ],
    );


  const reportClockTime =
    useCallback(
      (
        isoTime: string
      ) => {
        setCurrentTime(
          current =>
            current === isoTime
              ? current
              : isoTime
        );
      },
      [],
    );


  const seekToTime =
    useCallback(
      (
        isoTime: string
      ) => {
        if (!playback) {
          return false;
        }


        const target =
          new Date(
            isoTime
          ).getTime();

        const start =
          new Date(
            playback.start
          ).getTime();

        const end =
          new Date(
            playback.end
          ).getTime();


        if (
          !Number.isFinite(
            target
          )
          || target < start
          || target > end
        ) {
          return false;
        }


        const normalized =
          new Date(
            target
          ).toISOString();


        setCurrentTime(
          normalized
        );


        setSeekRequest(
          current => ({
            id:
              (
                current
                  ?.id
                ?? 0
              )
              + 1,

            at:
              normalized,
          })
        );


        return true;
      },
      [
        playback,
      ],
    );


  const seekToFraction =
    useCallback(
      (
        fraction: number
      ) => {
        if (!playback) {
          return;
        }


        const clamped =
          Math.max(
            0,
            Math.min(
              1,
              fraction
            )
          );


        const start =
          new Date(
            playback.start
          ).getTime();

        const end =
          new Date(
            playback.end
          ).getTime();


        const target =
          new Date(
            start
            + (
              end - start
            )
            * clamped
          ).toISOString();


        setCurrentTime(
          target
        );


        setSeekRequest(
          current => ({
            id:
              (
                current
                  ?.id
                ?? 0
              )
              + 1,

            at:
              target,
          })
        );
      },
      [
        playback,
      ],
    );


  const progress =
    useMemo(
      () => {
        if (
          !playback
          || !currentTime
        ) {
          return 0;
        }


        const start =
          new Date(
            playback.start
          ).getTime();

        const end =
          new Date(
            playback.end
          ).getTime();

        const current =
          new Date(
            currentTime
          ).getTime();


        if (
          !Number.isFinite(
            start
          )
          || !Number.isFinite(
            end
          )
          || !Number.isFinite(
            current
          )
          || end <= start
        ) {
          return 0;
        }


        return Math.max(
          0,
          Math.min(
            1,
            (
              current - start
            )
            / (
              end - start
            )
          )
        );
      },
      [
        playback,
        currentTime,
      ],
    );


  const reload =
    useCallback(
      () => {
        if (
          selectedObjectIds.length
          > 0
        ) {
          void loadForObjects(
            selectedObjectIds,
            false,
          );

          return;
        }


        if (autoload) {
          setReloadKey(
            current =>
              current + 1
          );
        }
      },
      [
        autoload,
        loadForObjects,
        selectedObjectIds,
      ],
    );


  return (
    <OrbitalPlaybackContext.Provider
      value={{
        playback,
        selectedObjectId,
        selectedObjectIds,
        loadedObjectIds,
        loadForObjects,
        loading,
        error,
        isPlaying,
        setIsPlaying,
        speed,
        setSpeed,
        currentTime,
        progress,
        seekRequest,
        seekToTime,
        seekToFraction,
        reportClockTime,
        reload,
      }}
    >
      {children}
    </OrbitalPlaybackContext.Provider>
  );
}


export function useOrbitalPlayback() {
  const context =
    useContext(
      OrbitalPlaybackContext
    );


  if (!context) {
    throw new Error(
      "useOrbitalPlayback must be used inside OrbitalPlaybackProvider"
    );
  }


  return context;
}
