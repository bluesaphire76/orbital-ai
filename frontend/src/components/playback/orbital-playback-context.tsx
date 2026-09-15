"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
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


interface OrbitalPlaybackContextValue {
  playback:
    VisualizationPlayback | null;

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
  children,
}: {
  initialSnapshotAt:
    string | null;

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
  ] = useState(true);

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
  >(null);

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


  useEffect(() => {
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
    initialSnapshotAt,
    reloadKey,
  ]);


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
        setReloadKey(
          current =>
            current + 1
        );
      },
      [],
    );


  return (
    <OrbitalPlaybackContext.Provider
      value={{
        playback,
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
