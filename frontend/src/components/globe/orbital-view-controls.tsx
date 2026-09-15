"use client";

import {
  useOrbitalView,
} from "@/components/globe/orbital-view-context";


export function OrbitalViewControls() {
  const {
    layers,
    setLayers,
    viewMode,
    setViewMode,
    imageryMode,
    setImageryMode,
  } = useOrbitalView();


  function setLayer(
    key:
      keyof typeof layers,
    value:
      boolean,
  ) {
    setLayers(
      current => ({
        ...current,
        [key]: value,
      })
    );
  }


  return (
    <>
      <div className="sidebarSection">

        <span className="sectionLabel">
          CAMERA
        </span>


        <div className="segmentedControl">

          <button
            className={
              viewMode === "orbit"
                ? "active"
                : ""
            }
            onClick={() =>
              setViewMode(
                "orbit"
              )
            }
            type="button"
          >
            ORBIT
          </button>


          <button
            className={
              viewMode === "pan"
                ? "active"
                : ""
            }
            onClick={() =>
              setViewMode(
                "pan"
              )
            }
            type="button"
          >
            PAN
          </button>

        </div>


        <div className="controlHint">
          {
            viewMode === "orbit"
              ? "Drag to rotate Earth"
              : "Drag to move Earth in the viewport"
          }
        </div>

      </div>


      <div className="sidebarSection">

        <span className="sectionLabel">
          EARTH
        </span>


        <label className="layerRow">
          <input
            checked={
              imageryMode
              === "satellite"
            }
            name="earth-imagery"
            onChange={() =>
              setImageryMode(
                "satellite"
              )
            }
            type="radio"
          />

          <span>
            Satellite
          </span>

          <small>
            NASA
          </small>
        </label>


        <label className="layerRow">
          <input
            checked={
              imageryMode
              === "local"
            }
            name="earth-imagery"
            onChange={() =>
              setImageryMode(
                "local"
              )
            }
            type="radio"
          />

          <span>
            Local
          </span>

          <small>
            Offline
          </small>
        </label>

      </div>


      <div className="sidebarSection">

        <span className="sectionLabel">
          LAYERS
        </span>


        <label className="layerRow">
          <input
            checked={
              layers.objects
            }
            onChange={
              event =>
                setLayer(
                  "objects",
                  event
                    .target
                    .checked,
                )
            }
            type="checkbox"
          />

          <span>
            Orbital objects
          </span>
        </label>


        <label className="layerRow">
          <input
            checked={
              layers.labels
            }
            onChange={
              event =>
                setLayer(
                  "labels",
                  event
                    .target
                    .checked,
                )
            }
            type="checkbox"
          />

          <span>
            Object labels
          </span>
        </label>


        <label className="layerRow">
          <input
            checked={
              layers.trajectories
            }
            onChange={
              event =>
                setLayer(
                  "trajectories",
                  event
                    .target
                    .checked,
                )
            }
            type="checkbox"
          />

          <span>
            Trajectories
          </span>
        </label>


        <label className="layerRow">
          <input
            checked={
              layers.conjunctions
            }
            onChange={
              event =>
                setLayer(
                  "conjunctions",
                  event
                    .target
                    .checked,
                )
            }
            type="checkbox"
          />

          <span>
            Conjunctions
          </span>
        </label>

      </div>
    </>
  );
}
