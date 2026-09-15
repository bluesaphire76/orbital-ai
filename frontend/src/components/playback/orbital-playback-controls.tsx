"use client";

import {
  useOrbitalPlayback,
  type PlaybackSpeed,
} from "@/components/playback/orbital-playback-context";


const SPEEDS:
  PlaybackSpeed[] = [
    1,
    10,
    100,
    1000,
  ];


function formatUtc(
  value: string | null,
) {
  if (!value) {
    return "—";
  }


  const date =
    new Date(
      value
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return "—";
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


export function OrbitalPlaybackControls({
  fallbackFrame,
}: {
  fallbackFrame: string;
}) {
  const {
    playback,
    loading,
    error,
    isPlaying,
    setIsPlaying,
    speed,
    setSpeed,
    currentTime,
    progress,
    seekToFraction,
    reload,
  } = useOrbitalPlayback();


  return (
    <>
      <button
        className="playButton"
        disabled={
          !playback
          || loading
        }
        onClick={() =>
          setIsPlaying(
            current =>
              !current
          )
        }
        type="button"
      >
        <span className="playButtonIcon">
          {
            isPlaying
              ? "❚❚"
              : "▶"
          }
        </span>

        <span>
          {
            isPlaying
              ? "PAUSE"
              : "PLAY"
          }
        </span>
      </button>


      <div className="timeReadout">
        <span>
          SIMULATION UTC
        </span>

        <strong>
          {
            loading
              ? "LOADING..."
              : formatUtc(
                  currentTime
                )
          }
        </strong>

        {error && (
          <button
            className="timelineRetry"
            onClick={reload}
            type="button"
          >
            RETRY
          </button>
        )}
      </div>


      <div className="timelinePlayback">

        <input
          aria-label="Playback timeline"
          className="timelineScrubber"
          disabled={
            !playback
            || loading
          }
          max={1000}
          min={0}
          onChange={
            event =>
              seekToFraction(
                Number(
                  event
                    .target
                    .value
                )
                / 1000
              )
          }
          step={1}
          type="range"
          value={
            Math.round(
              progress
              * 1000
            )
          }
        />


        <div className="playbackSpeeds">

          {SPEEDS.map(
            candidate => (
              <button
                className={
                  speed
                  === candidate
                    ? "active"
                    : ""
                }
                disabled={
                  !playback
                }
                key={
                  candidate
                }
                onClick={() =>
                  setSpeed(
                    candidate
                  )
                }
                type="button"
              >
                {candidate}x
              </button>
            )
          )}

        </div>

      </div>


      <div className="timeReadout right">
        <span>
          REFERENCE FRAME
        </span>

        <strong>
          {
            playback
              ?.frame
            ?? fallbackFrame
          }
        </strong>

        {playback && (
          <small>
            {
              playback
                .rendered_objects
            } OBJECTS · {
              playback
                .step_seconds
            }s SAMPLES
          </small>
        )}
      </div>
    </>
  );
}
