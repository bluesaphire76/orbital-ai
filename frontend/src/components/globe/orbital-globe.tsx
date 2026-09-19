"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  useOrbitalView,
} from "@/components/globe/orbital-view-context";

import {
  useOrbitalPlayback,
} from "@/components/playback/orbital-playback-context";

import {
  useConjunctionFocus,
} from "@/components/conjunction/conjunction-focus-context";

import type {
  ConjunctionEvent,
} from "@/types/conjunction";


import type {
  ObjectTrajectory,
  VisualizationObject,
  VisualizationSnapshot,
} from "@/types/visualization";


type CesiumWindow =
  Window & {
    CESIUM_BASE_URL?: string;
  };


interface OrbitalGlobeProps {
  snapshot:
    VisualizationSnapshot | null;

  conjunctionEvents:
    ConjunctionEvent[];
}


interface PickMovement {
  position:
    import("cesium").Cartesian2;
}


type OrbitalObjectKind =
  | "PAYLOAD"
  | "DEBRIS"
  | "ROCKET_BODY"
  | "UNKNOWN";


const ORBITAL_OBJECT_KINDS:
  OrbitalObjectKind[] = [
    "PAYLOAD",
    "DEBRIS",
    "ROCKET_BODY",
    "UNKNOWN",
  ];


const ORBITAL_OBJECT_VISUALS:
  Record<
    OrbitalObjectKind,
    {
      label: string;
      color: string;
    }
  > = {
    PAYLOAD: {
      label:
        "Payload / Satellite",
      color:
        "#56d9ef",
    },

    DEBRIS: {
      label:
        "Debris",
      color:
        "#ef8c55",
    },

    ROCKET_BODY: {
      label:
        "Rocket Body",
      color:
        "#f1c75b",
    },

    UNKNOWN: {
      label:
        "Unknown / Other",
      color:
        "#f4f7fb",
    },
  };


function normalizeOrbitalObjectKind(
  value:
    string
    | null
    | undefined,
): OrbitalObjectKind {
  const normalized =
    (
      value
      ?? "UNKNOWN"
    )
      .trim()
      .toUpperCase()
      .replaceAll(
        " ",
        "_",
      )
      .replaceAll(
        "-",
        "_",
      );


  switch (normalized) {
    case "PAYLOAD":
      return "PAYLOAD";

    case "DEBRIS":
      return "DEBRIS";

    case "ROCKET_BODY":
      return "ROCKET_BODY";

    default:
      return "UNKNOWN";
  }
}


function orbitalObjectColorHex(
  value:
    string
    | null
    | undefined,
) {
  return (
    ORBITAL_OBJECT_VISUALS[
      normalizeOrbitalObjectKind(
        value
      )
    ].color
  );
}


function velocityKmS(
  object: VisualizationObject,
) {
  return (
    Math.sqrt(
      object.vx_m_s ** 2
      + object.vy_m_s ** 2
      + object.vz_m_s ** 2,
    )
    / 1000.0
  );
}


function approximateAltitudeKm(
  object: VisualizationObject,
) {
  const radius =
    Math.sqrt(
      object.x_m ** 2
      + object.y_m ** 2
      + object.z_m ** 2,
    );

  return (
    radius - 6_378_137
  ) / 1000.0;
}


const OPERATIONAL_STATUS_LABELS:
  Record<string, string> = {
    "+": "Operational",
    "-": "Nonoperational",
    "P": "Partially Operational",
    "B": "Backup / Standby",
    "S": "Spare",
    "X": "Extended Mission",
    "D": "Decayed",
    "?": "Unknown",
  };


function formatOperationalStatus(
  value: string | null,
) {
  if (!value) {
    return "Unknown";
  }


  const label =
    OPERATIONAL_STATUS_LABELS[
      value
    ];


  if (!label) {
    return value;
  }


  return `${label} (${value})`;
}


export function OrbitalGlobe({
  snapshot,
  conjunctionEvents,
}: OrbitalGlobeProps) {
  const {
    layers,
    viewMode,
    imageryMode,
  } = useOrbitalView();

  const {
    playback,
    isPlaying,
    speed,
    seekRequest,
    reportClockTime,
    setIsPlaying,
  } = useOrbitalPlayback();

  const {
    activeEventId:
      activeConjunctionEventId,
  } = useConjunctionFocus();
  const containerRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const viewerRef =
    useRef<
      import("cesium").Viewer | null
    >(null);

  const cityLightsPrimitiveRef =
    useRef<
      import("cesium").Primitive | null
    >(null);

  const mapCameraControllerRef =
    useRef<
      import("cesium")
        .ScreenSpaceMapCameraController
      | null
    >(
      null
    );

  const layersRef =
    useRef(
      layers
    );

  const selectedIdsRef =
    useRef<Set<number>>(
      new Set(),
    );

  const activeObjectIdRef =
    useRef<number | null>(
      null,
    );

  const cameraLockedRef =
    useRef(false);


  const clearSelectionRef =
    useRef<() => void>(
      () => undefined,
    );

  const removeSelectionRef =
    useRef<(id: number) => void>(
      () => undefined,
    );

  const focusObjectRef =
    useRef<(id: number) => void>(
      () => undefined,
    );

  const toggleCameraLockRef =
    useRef<() => void>(
      () => undefined,
    );


  const [
    ready,
    setReady,
  ] = useState(false);

  const [
    selectedIds,
    setSelectedIds,
  ] = useState<number[]>(
    [],
  );

  const [
    activeObjectId,
    setActiveObjectId,
  ] = useState<number | null>(
    null,
  );


  const [
    isolateSelection,
    setIsolateSelection,
  ] = useState(false);


  /*
   * Publish the active object outside the globe
   * without moving Cesium selection state into
   * a shared React context.
   *
   * Playback/search can subscribe to this event
   * while OrbitalGlobe remains authoritative for
   * visual selection, flyTo and tracking.
   */
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent(
        "orbitalai:active-object-change",
        {
          detail: {
            objectId: activeObjectId,
          },
        },
      ),
    );
  }, [
    activeObjectId,
  ]);



  /*
   * Publish the complete visual selection for
   * targeted multi-object playback.
   *
   * OrbitalGlobe remains authoritative for
   * selection itself.
   */
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent(
        "orbitalai:selected-objects-change",
        {
          detail: {
            objectIds:
              selectedIds,
          },
        },
      ),
    );
  }, [
    selectedIds,
  ]);

  const [
    cameraLocked,
    setCameraLocked,
  ] = useState(false);

  const [
    loadingIds,
    setLoadingIds,
  ] = useState<number[]>(
    [],
  );

  const [
    trajectoryError,
    setTrajectoryError,
  ] = useState<
    string | null
  >(null);


  const [
    legendOpen,
    setLegendOpen,
  ] = useState(false);


  const objectLegend =
    useMemo(
      () => {
        const counts:
          Record<
            OrbitalObjectKind,
            number
          > = {
            PAYLOAD: 0,
            DEBRIS: 0,
            ROCKET_BODY: 0,
            UNKNOWN: 0,
          };


        for (
          const object
          of snapshot?.objects
          ?? []
        ) {
          const kind =
            normalizeOrbitalObjectKind(
              object.object_type
            );

          counts[kind] += 1;
        }


        return (
          ORBITAL_OBJECT_KINDS
            .map(
              kind => ({
                kind,

                label:
                  ORBITAL_OBJECT_VISUALS[
                    kind
                  ].label,

                color:
                  ORBITAL_OBJECT_VISUALS[
                    kind
                  ].color,

                count:
                  counts[kind],
              })
            )
        );
      },

      [
        snapshot,
      ],
    );


  useEffect(() => {
    let disposed = false;

    let handler:
      import("cesium")
        .ScreenSpaceEventHandler
      | null = null;


    async function initialize() {
      if (
        !containerRef.current
      ) {
        return;
      }


      (
        window as CesiumWindow
      ).CESIUM_BASE_URL =
        "/cesium/";


      const Cesium =
        await import(
          "cesium"
        );


      if (
        disposed
        || !containerRef.current
      ) {
        return;
      }


      const viewer =
        new Cesium.Viewer(
          containerRef.current,
          {
            animation: false,
            baseLayer: false,
            baseLayerPicker: false,
            fullscreenButton: false,
            geocoder: false,
            homeButton: false,
            infoBox: false,
            navigationHelpButton:
              false,
            sceneModePicker: false,
            selectionIndicator:
              false,
            timeline: false,

            terrainProvider:
              new Cesium
                .EllipsoidTerrainProvider(),

            shouldAnimate:
              false,

            requestRenderMode:
              false,

            scene3DOnly:
              true,
          },
        );


      viewerRef.current =
        viewer;


      const mapCameraController =
        new Cesium
          .ScreenSpaceMapCameraController();


      mapCameraController.enabled =
        false;


      viewer.addController(
        mapCameraController
      );


      mapCameraControllerRef.current =
        mapCameraController;


      viewer.screenSpaceEventHandler
        .removeInputAction(
          Cesium
            .ScreenSpaceEventType
            .LEFT_DOUBLE_CLICK,
        );


      if (disposed) {
        viewer.destroy();
        return;
      }


      viewer.scene.backgroundColor =
        Cesium.Color.fromCssColorString(
          "#010308",
        );


      viewer.scene.globe.baseColor =
        Cesium.Color.fromCssColorString(
          "#06111c",
        );


      viewer.scene.globe
        .showGroundAtmosphere =
        true;


      viewer.scene
        .screenSpaceCameraController
        .enableCollisionDetection =
        false;


      viewer.camera.setView({
        destination:
          Cesium.Cartesian3
            .fromDegrees(
              8.0,
              20.0,
              22_000_000,
            ),
      });


      const objectsById =
        new Map<
          number,
          VisualizationObject
        >(
          (
            snapshot
              ?.objects
            ?? []
          ).map(
            object => [
              object.object_id,
              object,
            ],
          ),
        );


      function objectColor(
        objectType:
          string
          | null
          | undefined,
      ) {
        return Cesium.Color
          .fromCssColorString(
            orbitalObjectColorHex(
              objectType
            )
          );
      }


      if (snapshot) {
        for (
          const object
          of snapshot.objects
        ) {
          const color =
            objectColor(
              object.object_type,
            );


          viewer.entities.add({
            id:
              `orbital-object-${object.object_id}`,

            name:
              object.object_name,

            position:
              Cesium.Cartesian3
                .fromElements(
                  object.x_m,
                  object.y_m,
                  object.z_m,
                ),

            point: {
              show:
                layersRef.current
                  .objects,

              pixelSize: 7,

              color,

              outlineColor:
                Cesium.Color
                  .BLACK,

              outlineWidth: 1,

              scaleByDistance:
                new Cesium
                  .NearFarScalar(
                    1_000_000,
                    1.35,
                    50_000_000,
                    0.85,
                  ),
            },

            label: {
              show:
                layersRef.current
                  .labels,

              text:
                object.object_name,

              font:
                "10px monospace",

              fillColor:
                Cesium.Color
                  .WHITE,

              showBackground:
                true,

              backgroundColor:
                Cesium.Color
                  .BLACK
                  .withAlpha(
                    0.55,
                  ),

              pixelOffset:
                new Cesium
                  .Cartesian2(
                    9,
                    -11,
                  ),

              distanceDisplayCondition:
                new Cesium
                  .DistanceDisplayCondition(
                    0,
                    50_000_000,
                  ),

              scaleByDistance:
                new Cesium
                  .NearFarScalar(
                    2_000_000,
                    1.0,
                    50_000_000,
                    0.65,
                  ),
            },
          });
        }
      }


      function syncSelectedState() {
        setSelectedIds(
          Array.from(
            selectedIdsRef.current,
          ),
        );
      }


      function setVisualSelection(
        objectId: number,
        selected: boolean,
      ) {
        const entity =
          viewer.entities.getById(
            `orbital-object-${objectId}`,
          );

        if (
          !entity
          || !entity.point
        ) {
          return;
        }


        entity.point.pixelSize =
          new Cesium.ConstantProperty(
            selected
              ? 12
              : 7,
          );


        entity.point.outlineWidth =
          new Cesium.ConstantProperty(
            selected
              ? 2
              : 1,
          );


        entity.point.outlineColor =
          new Cesium.ConstantProperty(
            selected
              ? Cesium.Color.WHITE
              : Cesium.Color.BLACK,
          );
      }


      function clearSelection(
        resetIsolation = true,
      ) {
        for (
          const objectId
          of selectedIdsRef.current
        ) {
          setVisualSelection(
            objectId,
            false,
          );

          viewer.entities.removeById(
            `trajectory-${objectId}`,
          );
        }


        selectedIdsRef.current =
          new Set();

        activeObjectIdRef.current =
          null;


        viewer.selectedEntity =
          undefined;

        viewer.trackedEntity =
          undefined;


        setSelectedIds(
          [],
        );

        setActiveObjectId(
          null,
        );

        setTrajectoryError(
          null,
        );


        if (resetIsolation) {
          setIsolateSelection(
            false
          );
        }
      }


      function removeSelection(
        objectId: number,
      ) {
        if (
          !selectedIdsRef.current
            .has(
              objectId
            )
        ) {
          return;
        }


        selectedIdsRef.current
          .delete(
            objectId
          );


        if (
          selectedIdsRef.current.size
          === 0
        ) {
          setIsolateSelection(
            false
          );
        }


        setVisualSelection(
          objectId,
          false,
        );


        viewer.entities.removeById(
          `trajectory-${objectId}`,
        );


        if (
          activeObjectIdRef.current
          === objectId
        ) {
          const remaining =
            Array.from(
              selectedIdsRef.current,
            );


          const nextActive =
            remaining.length > 0
              ? remaining[
                  remaining.length - 1
                ]
              : null;


          activeObjectIdRef.current =
            nextActive;


          setActiveObjectId(
            nextActive,
          );


          if (
            nextActive === null
          ) {
            viewer.selectedEntity =
              undefined;

            viewer.trackedEntity =
              undefined;

          } else {
            const nextEntity =
              viewer.entities
                .getById(
                  `orbital-object-${nextActive}`,
                );


            viewer.selectedEntity =
              nextEntity;


            viewer.trackedEntity =
              cameraLockedRef.current
                ? nextEntity
                : undefined;
          }
        }


        syncSelectedState();
      }


      async function loadStaticTrajectory(
        objectId: number,
      ) {
        if (!snapshot) {
          return;
        }


        setLoadingIds(
          current =>
            current.includes(
              objectId
            )
              ? current
              : [
                  ...current,
                  objectId,
                ]
        );

        setTrajectoryError(
          null
        );


        try {
          const center =
            new Date(
              snapshot.at
            );


          if (
            Number.isNaN(
              center.getTime()
            )
          ) {
            throw new Error(
              "Invalid snapshot time"
            );
          }


          const start =
            new Date(
              center.getTime()
              - 45
              * 60
              * 1000
            );

          const end =
            new Date(
              center.getTime()
              + 45
              * 60
              * 1000
            );


          const params =
            new URLSearchParams({
              start:
                start.toISOString(),

              end:
                end.toISOString(),

              step_seconds:
                "60",
            });


          const response =
            await fetch(
              `/api/visualization/objects/${objectId}/trajectory?${params}`,
              {
                cache:
                  "no-store",
              },
            );


          if (!response.ok) {
            throw new Error(
              `Trajectory request failed (${response.status})`
            );
          }


          const trajectory =
            (
              await response.json()
            ) as ObjectTrajectory;


          if (
            !selectedIdsRef.current
              .has(
                objectId
              )
          ) {
            return;
          }


          const positions =
            trajectory.points.map(
              point =>
                Cesium
                  .Cartesian3
                  .fromElements(
                    point.x_m,
                    point.y_m,
                    point.z_m,
                  )
            );


          viewer.entities.removeById(
            `trajectory-${objectId}`,
          );


          viewer.entities.add({
            id:
              `trajectory-${objectId}`,

            show:
              layersRef.current
                .trajectories,

            polyline: {
              positions,

              width:
                2.2,

              material:
                Cesium.Color
                  .fromCssColorString(
                    "#55d6ef"
                  )
                  .withAlpha(
                    0.84
                  ),
            },
          });

        } catch (error) {
          setTrajectoryError(
            error
            instanceof Error
              ? error.message
              : "Trajectory loading failed"
          );

        } finally {
          setLoadingIds(
            current =>
              current.filter(
                id =>
                  id !== objectId
              )
          );
        }
      }


      async function focusObject(
        objectId: number,
      ) {
        const entity =
          viewer.entities.getById(
            `orbital-object-${objectId}`,
          );


        if (!entity) {
          return;
        }


        activeObjectIdRef.current =
          objectId;

        setActiveObjectId(
          objectId,
        );


        viewer.selectedEntity =
          entity;


        /*
         * flyTo cancels existing
         * entity tracking, therefore
         * trackedEntity is set only
         * after the flight completes.
         */
        const completed =
          await viewer.flyTo(
            entity,
            {
              duration: 0.8,

              offset:
                new Cesium
                  .HeadingPitchRange(
                    0,

                    Cesium.Math
                      .toRadians(
                        -25,
                      ),

                    1_500_000,
                  ),
            },
          );


        if (
          completed
          && cameraLockedRef.current
        ) {
          viewer.trackedEntity =
            entity;
        }
      }


      async function selectObject(
        objectId: number,
        additive: boolean,
      ) {
        const object =
          objectsById.get(
            objectId
          );


        if (!object) {
          return;
        }


        if (
          additive
          && selectedIdsRef.current
            .has(
              objectId
            )
        ) {
          removeSelection(
            objectId
          );

          return;
        }


        if (!additive) {
          clearSelection(
            false
          );
        }


        if (
          !selectedIdsRef.current
            .has(
              objectId
            )
        ) {
          selectedIdsRef.current
            .add(
              objectId
            );


          setVisualSelection(
            objectId,
            true,
          );


          syncSelectedState();


          void loadStaticTrajectory(
            objectId
          );
        }


        await focusObject(
          objectId
        );
      }


      function pickObject(
        movement: PickMovement,
        additive: boolean,
      ) {
        const picked =
          viewer.scene.pick(
            movement.position,
          );


        if (
          !Cesium.defined(
            picked
          )
          || !picked.id
        ) {
          if (!additive) {
            clearSelection();
          }

          return;
        }


        const entity =
          picked.id as
            import("cesium")
              .Entity;


        if (
          !entity.id.startsWith(
            "orbital-object-",
          )
        ) {
          if (!additive) {
            clearSelection();
          }

          return;
        }


        const objectId =
          Number(
            entity.id.replace(
              "orbital-object-",
              "",
            ),
          );


        void selectObject(
          objectId,
          additive,
        );
      }


      function toggleCameraLock() {
        cameraLockedRef.current =
          !cameraLockedRef.current;


        setCameraLocked(
          cameraLockedRef.current,
        );


        if (
          !cameraLockedRef.current
        ) {
          viewer.trackedEntity =
            undefined;

          return;
        }


        const objectId =
          activeObjectIdRef.current;


        if (
          objectId === null
        ) {
          return;
        }


        const entity =
          viewer.entities.getById(
            `orbital-object-${objectId}`,
          );


        viewer.trackedEntity =
          entity;
      }


      clearSelectionRef.current =
        clearSelection;

      removeSelectionRef.current =
        removeSelection;

      focusObjectRef.current =
        objectId => {
          void focusObject(
            objectId
          );
        };

      toggleCameraLockRef.current =
        toggleCameraLock;


      handler =
        new Cesium
          .ScreenSpaceEventHandler(
            viewer.scene.canvas,
          );


      handler.setInputAction(
        (
          movement:
            PickMovement
        ) => {
          pickObject(
            movement,
            false,
          );
        },

        Cesium
          .ScreenSpaceEventType
          .LEFT_CLICK,
      );


      handler.setInputAction(
        (
          movement:
            PickMovement
        ) => {
          pickObject(
            movement,
            true,
          );
        },

        Cesium
          .ScreenSpaceEventType
          .LEFT_CLICK,

        Cesium
          .KeyboardEventModifier
          .CTRL,
      );


      handler.setInputAction(
        (
          movement:
            PickMovement
        ) => {
          pickObject(
            movement,
            true,
          );
        },

        Cesium
          .ScreenSpaceEventType
          .LEFT_CLICK,

        Cesium
          .KeyboardEventModifier
          .SHIFT,
      );


      function handleKeyDown(
        event: KeyboardEvent,
      ) {
        if (
          event.key === "Escape"
        ) {
          clearSelection();
        }
      }


      function publishCatalog() {
        window.dispatchEvent(
          new CustomEvent(
            "orbitalai:catalog-available",
            {
              detail: {
                objects:
                  snapshot?.objects
                  ?? [],
              },
            },
          ),
        );
      }


      function handleCatalogRequest() {
        publishCatalog();
      }


      function handleSelectObjectRequest(
        event: Event,
      ) {
        const customEvent =
          event as CustomEvent<{
            objectId:
              number;

            additive?:
              boolean;
          }>;


        const objectId =
          customEvent.detail
            ?.objectId;


        if (
          !Number.isInteger(
            objectId
          )
        ) {
          return;
        }


        void selectObject(
          objectId,
          Boolean(
            customEvent.detail
              ?.additive
          ),
        );
      }


      function handleSelectConjunctionPairRequest(
        event: Event,
      ) {
        const customEvent =
          event as CustomEvent<{
            primaryObjectId:
              number;

            secondaryObjectId:
              number;
          }>;


        const primaryObjectId =
          customEvent.detail
            ?.primaryObjectId;

        const secondaryObjectId =
          customEvent.detail
            ?.secondaryObjectId;


        if (
          !Number.isInteger(
            primaryObjectId
          )
          || !Number.isInteger(
            secondaryObjectId
          )
          || primaryObjectId
            === secondaryObjectId
        ) {
          return;
        }


        const primaryEntity =
          viewer.entities.getById(
            `orbital-object-${primaryObjectId}`
          );

        const secondaryEntity =
          viewer.entities.getById(
            `orbital-object-${secondaryObjectId}`
          );


        if (
          !primaryEntity
          || !secondaryEntity
        ) {
          return;
        }


        clearSelection(
          false
        );


        selectedIdsRef.current =
          new Set([
            primaryObjectId,
            secondaryObjectId,
          ]);


        setVisualSelection(
          primaryObjectId,
          true,
        );

        setVisualSelection(
          secondaryObjectId,
          true,
        );


        activeObjectIdRef.current =
          primaryObjectId;

        setActiveObjectId(
          primaryObjectId
        );

        viewer.selectedEntity =
          primaryEntity;


        syncSelectedState();


        setIsolateSelection(
          true
        );
      }


      window.addEventListener(
        "orbitalai:catalog-request",
        handleCatalogRequest,
      );

      window.addEventListener(
        "orbitalai:select-object",
        handleSelectObjectRequest,
      );

      window.addEventListener(
        "orbitalai:select-conjunction-pair",
        handleSelectConjunctionPairRequest,
      );

      window.addEventListener(
        "keydown",
        handleKeyDown,
      );


      publishCatalog();


      if (!disposed) {
        setReady(
          true
        );
      }


      return () => {
        window.removeEventListener(
          "orbitalai:catalog-request",
          handleCatalogRequest,
        );

        window.removeEventListener(
          "orbitalai:select-object",
          handleSelectObjectRequest,
        );

        window.removeEventListener(
          "orbitalai:select-conjunction-pair",
          handleSelectConjunctionPairRequest,
        );

        window.removeEventListener(
          "keydown",
          handleKeyDown,
        );
      };
    }


    let removeKeyboardHandler:
      (() => void)
      | undefined;


    void initialize().then(
      cleanup => {
        removeKeyboardHandler =
          cleanup;
      },
    );


    return () => {
      disposed =
        true;


      removeKeyboardHandler?.();


      if (
        handler
        && !handler.isDestroyed()
      ) {
        handler.destroy();
      }


      if (
        viewerRef.current
        && !viewerRef.current
          .isDestroyed()
      ) {
        viewerRef.current
          .destroy();
      }


      viewerRef.current =
        null;
    };

  }, [snapshot]);


  useEffect(() => {
    layersRef.current =
      layers;


    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
    ) {
      return;
    }


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          viewer.isDestroyed()
        ) {
          return;
        }


        for (
          const entity
          of viewer.entities.values
        ) {
          if (
            entity.id.startsWith(
              "orbital-object-"
            )
          ) {
            const objectId =
              Number(
                entity.id.replace(
                  "orbital-object-",
                  "",
                )
              );


            const objectVisible =
              layers.objects
              && (
                !isolateSelection
                || selectedIds.includes(
                  objectId
                )
              );


            if (entity.point) {
              entity.point.show =
                new Cesium
                  .ConstantProperty(
                    objectVisible
                  );
            }


            if (entity.label) {
              entity.label.show =
                new Cesium
                  .ConstantProperty(
                    layers.labels
                    && objectVisible
                  );
            }


            if (entity.path) {
              entity.path.show =
                new Cesium
                  .ConstantProperty(
                    layers
                      .trajectories
                  );
            }

            continue;
          }


          if (
            entity.id.startsWith(
              "trajectory-"
            )
          ) {
            entity.show =
              layers.trajectories;

            continue;
          }


          if (
            entity.id.startsWith(
              "conjunction-"
            )
          ) {
            entity.show =
              layers.conjunctions;
          }
        }
      }
    );

  }, [
    isolateSelection,
    layers,
    ready,
    selectedIds,
  ]);


  useEffect(() => {
    const viewer =
      viewerRef.current;

    const mapController =
      mapCameraControllerRef.current;


    if (
      !ready
      || !viewer
      || !mapController
      || viewer.isDestroyed()
    ) {
      return;
    }


    const standard =
      viewer.scene
        .screenSpaceCameraController;


    if (
      viewMode === "pan"
    ) {
      /*
       * Left-drag is handed to the
       * tangential map controller.
       * Wheel zoom remains enabled.
       */
      standard.enableRotate =
        false;

      standard.enableTilt =
        false;

      standard.enableLook =
        false;

      standard.enableZoom =
        true;

      mapController.enabled =
        true;

    } else {
      mapController.enabled =
        false;

      standard.enableRotate =
        true;

      standard.enableTilt =
        true;

      standard.enableLook =
        true;

      standard.enableZoom =
        true;
    }


    /*
     * Changing camera mode must
     * never clear selections.
     */
    viewer.trackedEntity =
      cameraLockedRef.current
        ? viewer.selectedEntity
        : undefined;

  }, [
    ready,
    viewMode,
  ]);


  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || viewer === null
      || viewer.isDestroyed()
    ) {
      return;
    }


    /*
     * Imagery and terrain are purely visual.
     * Authoritative orbital positions continue
     * to come from the backend.
     */
    const activeViewer =
      viewer;


    let cancelled =
      false;


    async function addNasaSatellite(
      Cesium:
        typeof import("cesium"),
    ) {
      const provider =
        new Cesium
          .WebMapServiceImageryProvider({
            url:
              "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi",

            layers:
              "BlueMarble_NextGeneration",

            parameters: {
              version:
                "1.3.0",

              format:
                "image/jpeg",

              transparent:
                "false",
            },

            enablePickFeatures:
              false,
          });


      if (
        cancelled
        || activeViewer
          .isDestroyed()
      ) {
        return;
      }


      activeViewer
        .imageryLayers
        .addImageryProvider(
          provider
        );
    }


    async function applyImagery() {
      const Cesium =
        await import(
          "cesium"
        );


      if (
        cancelled
        || activeViewer
          .isDestroyed()
      ) {
        return;
      }


      activeViewer
        .imageryLayers
        .removeAll();


      /*
       * Every non-HIGH-RES mode intentionally
       * returns to the local ellipsoid terrain.
       *
       * This also guarantees that LOCAL stays
       * independent from Cesium ion.
       */
      activeViewer
        .terrainProvider =
          new Cesium
            .EllipsoidTerrainProvider();


      const globe =
        activeViewer
          .scene
          .globe;


      /*
       * Conservative rendering defaults.
       * HIGH RES overrides these below.
       */
      activeViewer
        .useBrowserRecommendedResolution =
          true;

      activeViewer
        .resolutionScale =
          1.0;


      if (
        activeViewer
          .scene
          .msaaSupported
      ) {
        activeViewer
          .scene
          .msaaSamples =
            2;
      }


      globe.maximumScreenSpaceError =
        2.0;

      globe.tileCacheSize =
        100;


      globe.enableLighting =
        false;

      globe.dynamicAtmosphereLighting =
        false;

      globe.dynamicAtmosphereLightingFromSun =
        false;


      if (
        imageryMode
        === "local"
      ) {
        const provider =
          await Cesium
            .TileMapServiceImageryProvider
            .fromUrl(
              Cesium.buildModuleUrl(
                "Assets/Textures/NaturalEarthII"
              )
            );


        if (
          cancelled
          || activeViewer
            .isDestroyed()
        ) {
          return;
        }


        activeViewer
          .imageryLayers
          .addImageryProvider(
            provider
          );

        return;
      }


      if (
        imageryMode
        === "highres"
      ) {
        const token =
          process.env
            .NEXT_PUBLIC_CESIUM_ION_TOKEN
            ?.trim();


        if (!token) {
          console.warn(
            "Cesium ion token missing; "
            + "falling back to NASA imagery."
          );

          await addNasaSatellite(
            Cesium
          );

          return;
        }


        Cesium.Ion
          .defaultAccessToken =
            token;


        /*
         * HIGH RES profile:
         *
         * - render using the real device pixel ratio;
         * - keep native resolutionScale;
         * - refine terrain earlier;
         * - retain more terrain tiles for smoother
         *   orbital camera movement.
         */
        activeViewer
          .useBrowserRecommendedResolution =
            false;

        activeViewer
          .resolutionScale =
            1.0;

        globe.maximumScreenSpaceError =
          1.5;

        globe.tileCacheSize =
          128;


        try {
          const [
            imageryProvider,
            terrainProvider,
          ] =
            await Promise.all([
              Cesium
                .createWorldImageryAsync({
                  style:
                    Cesium
                      .IonWorldImageryStyle
                      .AERIAL,
                }),

              Cesium
                .createWorldTerrainAsync({
                  requestVertexNormals:
                    true,

                  requestWaterMask:
                    true,
                }),
            ]);


          if (
            cancelled
            || activeViewer
              .isDestroyed()
          ) {
            return;
          }


          activeViewer
            .imageryLayers
            .addImageryProvider(
              imageryProvider
            );


          activeViewer
            .terrainProvider =
              terrainProvider;



          /*
           * CITY LIGHTS
           *
           * Do NOT implement these as an ImageryLayer.
           * World Terrain uses vertex lighting, which
           * applies solar shading after imagery
           * compositing and would darken the night
           * texture itself.
           *
           * Instead render a thin, unlit emissive
           * shell slightly above the ellipsoid.
           */
          const previousCityLightsPrimitive =
            cityLightsPrimitiveRef.current;

          if (
            previousCityLightsPrimitive
            && !previousCityLightsPrimitive
              .isDestroyed()
          ) {
            activeViewer
              .scene
              .primitives
              .remove(
                previousCityLightsPrimitive
              );
          }


          const cityLightsMaterial =
            new Cesium.Material({
              fabric: {
                type:
                  "OrbitalAiCityLights",

                uniforms: {
                  image:
                    "/earth/black-marble-2016-3km.jpg",

                  intensity:
                    2.2,

                  opacity:
                    0.92,
                },

                source: `
                  czm_material czm_getMaterial(
                    czm_materialInput materialInput
                  )
                  {
                    czm_material material =
                      czm_getDefaultMaterial(
                        materialInput
                      );

                    vec4 nightTexture =
                      texture(
                        image,
                        materialInput.st
                      );

                    /*
                     * Positive sunDot = illuminated.
                     * Negative sunDot = night.
                     *
                     * This mask therefore follows the
                     * real Sun directly instead of
                     * Cesium ImageryLayer day/night
                     * alpha handling.
                     */
                    float sunDot =
                      dot(
                        normalize(
                          materialInput.normalEC
                        ),
                        normalize(
                          czm_sunDirectionEC
                        )
                      );

                    float nightMask =
                      1.0
                      - smoothstep(
                          -0.08,
                          0.12,
                          sunDot
                        );

                    /*
                     * Suppress Black Marble's dark
                     * land/ocean background and retain
                     * predominantly artificial lights.
                     */
                    float luminance =
                      dot(
                        nightTexture.rgb,
                        vec3(
                          0.2126,
                          0.7152,
                          0.0722
                        )
                      );

                    float lightMask =
                      smoothstep(
                        0.055,
                        0.24,
                        luminance
                      );

                    float alpha =
                      nightMask
                      * lightMask
                      * opacity;

                    /*
                     * Emission is intentionally used:
                     * city lights must remain bright
                     * when the solar-lit globe beneath
                     * them is dark.
                     */
                    material.diffuse =
                      vec3(0.0);

                    material.emission =
                      nightTexture.rgb
                      * intensity
                      * nightMask;

                    material.alpha =
                      alpha;

                    return material;
                  }
                `,
              },
            });


          const cityLightsGeometry =
            new Cesium.RectangleGeometry({
              rectangle:
                Cesium.Rectangle.MAX_VALUE,

              ellipsoid:
                Cesium.Ellipsoid.WGS84,

              /*
               * Small separation prevents z-fighting.
               * At orbital viewing distances this is
               * visually negligible.
               */
              height:
                2_500,

              vertexFormat:
                Cesium
                  .EllipsoidSurfaceAppearance
                  .VERTEX_FORMAT,
            });


          const cityLightsPrimitive =
            new Cesium.Primitive({
              geometryInstances:
                new Cesium.GeometryInstance({
                  geometry:
                    cityLightsGeometry,
                }),

              appearance:
                new Cesium
                  .EllipsoidSurfaceAppearance({
                    material:
                      cityLightsMaterial,

                    /*
                     * Critical:
                     * no solar lighting is applied to
                     * this shell after the material.
                     */
                    flat:
                      true,

                    translucent:
                      true,

                    aboveGround:
                      true,
                  }),

              asynchronous:
                false,
            });


          activeViewer
            .scene
            .primitives
            .add(
              cityLightsPrimitive
            );

          cityLightsPrimitiveRef.current =
            cityLightsPrimitive;


          globe.enableLighting =
            true;

          globe.dynamicAtmosphereLighting =
            true;

          globe.dynamicAtmosphereLightingFromSun =
            true;

          globe.showGroundAtmosphere =
            true;


          return;

        } catch (error) {
          console.error(
            "HIGH RES Earth failed; "
            + "falling back to NASA imagery.",
            error,
          );


          if (
            cancelled
            || activeViewer
              .isDestroyed()
          ) {
            return;
          }


          await addNasaSatellite(
            Cesium
          );

          return;
        }
      }


      await addNasaSatellite(
        Cesium
      );
    }


    void applyImagery();


    return () => {
      cancelled =
        true;
    };

  }, [
    imageryMode,
    ready,
  ]);


  /*
   * Space environment and solar illumination.
   *
   * This layer is visualization-only:
   * - the Earth skybox is bundled with Cesium;
   * - atmosphere is GPU-rendered;
   * - the day/night terminator follows the Cesium clock;
   * - no orbital mechanics are performed in the browser.
   *
   * Keep per-fragment atmosphere disabled because the
   * workstation GPU is also reserved for local LLM inference.
   */
  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || viewer === null
      || viewer.isDestroyed()
    ) {
      return;
    }


    let cancelled =
      false;


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          cancelled
          || viewer.isDestroyed()
        ) {
          return;
        }


        const scene =
          viewer.scene;

        const globe =
          scene.globe;


        /*
         * Ensure the native Cesium Earth star map
         * is available. No remote imagery service
         * is required for the stars.
         */
        if (!scene.skyBox) {
          scene.skyBox =
            Cesium
              .SkyBox
              .createEarthSkyBox();
        }


        scene.skyBox.show =
          true;


        /*
         * Ensure the atmospheric limb exists.
         */
        if (!scene.skyAtmosphere) {
          scene.skyAtmosphere =
            new Cesium
              .SkyAtmosphere(
                Cesium
                  .Ellipsoid
                  .WGS84
              );
        }


        const atmosphere =
          scene.skyAtmosphere;


        atmosphere.show =
          true;


        /*
         * Per-fragment atmosphere looks slightly
         * better but adds GPU work every frame.
         *
         * Leave it disabled for the shared
         * Cesium + llama.cpp GPU configuration.
         */
        atmosphere
          .perFragmentAtmosphere =
            false;


        /*
         * Do not enable terrain shadow-map passes.
         * The day/night terminator does not require
         * them and this saves GPU work and VRAM.
         */
        globe.shadows =
          Cesium
            .ShadowMode
            .DISABLED;


        if (
          imageryMode
          === "highres"
        ) {
          /*
           * Slightly darker atmosphere makes the
           * orbital view less washed-out and lets
           * the star field remain visible.
           */
          atmosphere
            .brightnessShift =
              -0.08;

          atmosphere
            .saturationShift =
              0.05;

          atmosphere
            .hueShift =
              0.0;

          atmosphere
            .atmosphereLightIntensity =
              48.0;


          /*
           * Real solar illumination.
           *
           * Because the light direction comes from
           * the Sun and Cesium's clock, the visible
           * day/night terminator moves naturally
           * with playback time.
           */
          /*
           * Solar illumination profile for the
           * orbital operations view.
           *
           * Cesium derives the Sun direction from
           * viewer.clock.currentTime, so playback
           * and conjunction TCA remain temporally
           * consistent with the visual terminator.
           */
          globe.enableLighting =
            true;

          globe
            .dynamicAtmosphereLighting =
              true;

          globe
            .dynamicAtmosphereLightingFromSun =
              true;

          globe
            .showGroundAtmosphere =
              true;


          /*
           * Keep the day side natural while making
           * the night hemisphere clearly readable
           * from orbital camera distances.
           */
          const earthRadius =
            globe
              .ellipsoid
              .minimumRadius;

          /*
           * Cesium-native solar lighting distances.
           *
           * Preserve a visible terminator while
           * avoiding an unnaturally crushed
           * night hemisphere.
           */
          globe
            .lightingFadeOutDistance =
              Math.PI
              * earthRadius
              * 0.5;

          globe
            .lightingFadeInDistance =
              Math.PI
              * earthRadius;

          globe
            .nightFadeOutDistance =
              Math.PI
              * earthRadius
              * 0.5;

          globe
            .nightFadeInDistance =
              Math.PI
              * earthRadius
              * 2.5;


          globe
            .atmosphereBrightnessShift =
              0.0;

          globe
            .atmosphereSaturationShift =
              0.0;

          globe
            .lambertDiffuseMultiplier =
              0.9;

          /*
           * Slightly soften terrain vertex
           * shadows without removing the
           * day/night distinction.
           */
          globe
            .vertexShadowDarkness =
              0.18;


          /*
           * Sun and Moon are cheap native Cesium
           * scene primitives and require no custom
           * textures or post-processing passes.
           */
          if (
            viewer
              .scene
              .sun
          ) {
            viewer
              .scene
              .sun
              .show =
                true;
          }

          if (
            viewer
              .scene
              .moon
          ) {
            viewer
              .scene
              .moon
              .show =
                true;
          }


        } else {
          /*
           * City lights belong only to the high-res
           * orbital rendering mode.
           */
          const cityLightsPrimitive =
            cityLightsPrimitiveRef.current;

          if (
            cityLightsPrimitive
            && !cityLightsPrimitive
              .isDestroyed()
          ) {
            viewer
              .scene
              .primitives
              .remove(
                cityLightsPrimitive
              );
          }

          cityLightsPrimitiveRef.current =
            null;


          /*
           * Keep the existing NASA/local modes
           * visually neutral.
           */
          atmosphere
            .brightnessShift =
              0.0;

          atmosphere
            .saturationShift =
              0.0;

          atmosphere
            .hueShift =
              0.0;

          atmosphere
            .atmosphereLightIntensity =
              50.0;


          globe.enableLighting =
            false;

          globe
            .dynamicAtmosphereLighting =
              false;

          globe
            .dynamicAtmosphereLightingFromSun =
              false;

          globe
            .atmosphereBrightnessShift =
              0.0;
        }
      }
    );


    return () => {
      cancelled =
        true;
    };

  }, [
    imageryMode,
    ready,
  ]);


  /*
   * Playback positions are generated
   * deterministically by the backend.
   *
   * Cesium only interpolates between
   * those authoritative samples for
   * visualization.
   */
  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !playback
    ) {
      return;
    }


    let cancelled =
      false;

    let removeTickListener:
      (() => void)
      | undefined;

    const temporaryPlaybackEntityIds:
      number[] = [];


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          cancelled
          || viewer.isDestroyed()
        ) {
          return;
        }


        const materializedObjectIds:
          number[] = [];


        for (
          const object
          of playback.objects
        ) {
          let entity =
            viewer.entities
              .getById(
                `orbital-object-${object.object_id}`
              );


          const position =
            new Cesium
              .SampledPositionProperty();


          for (
            const point
            of object.points
          ) {
            position.addSample(
              Cesium
                .JulianDate
                .fromIso8601(
                  point.at
                ),

              Cesium
                .Cartesian3
                .fromElements(
                  point.x_m,
                  point.y_m,
                  point.z_m,
                ),
            );
          }


          /*
           * Linear interpolation is
           * visualization-only.
           * Authoritative orbital positions
           * originate from the backend.
           */
          position
            .setInterpolationOptions({
              interpolationAlgorithm:
                Cesium
                  .LinearApproximation,

              interpolationDegree:
                1,
            });


          /*
           * A conjunction can reference an
           * object that is not renderable in
           * the current-time snapshot.
           *
           * Targeted playback is authoritative
           * for the requested TCA window, so
           * materialize a temporary Cesium
           * entity when the snapshot entity
           * does not exist.
           */
          if (!entity) {
            entity =
              viewer.entities.add({
                id:
                  `orbital-object-${object.object_id}`,

                name:
                  object.object_name,

                position,

                point: {
                  show:
                    layersRef.current
                      .objects,

                  pixelSize:
                    8,

                  color:
                    Cesium.Color
                      .fromCssColorString(
                        orbitalObjectColorHex(
                          object
                            .object_type
                        )
                      ),

                  outlineColor:
                    Cesium.Color
                      .BLACK,

                  outlineWidth:
                    1,

                  scaleByDistance:
                    new Cesium
                      .NearFarScalar(
                        1_000_000,
                        1.35,
                        50_000_000,
                        0.85,
                      ),
                },

                label: {
                  show:
                    layersRef.current
                      .labels,

                  text:
                    object.object_name,

                  font:
                    "10px monospace",

                  fillColor:
                    Cesium.Color
                      .WHITE,

                  showBackground:
                    true,

                  backgroundColor:
                    Cesium.Color
                      .BLACK
                      .withAlpha(
                        0.55
                      ),

                  pixelOffset:
                    new Cesium
                      .Cartesian2(
                        9,
                        -11,
                      ),

                  distanceDisplayCondition:
                    new Cesium
                      .DistanceDisplayCondition(
                        0,
                        50_000_000,
                      ),

                  scaleByDistance:
                    new Cesium
                      .NearFarScalar(
                        2_000_000,
                        1.0,
                        50_000_000,
                        0.65,
                      ),
                },
              });


            temporaryPlaybackEntityIds
              .push(
                object.object_id
              );

          } else {
            entity.position =
              position;
          }


          materializedObjectIds
            .push(
              object.object_id
            );
        }


        window.dispatchEvent(
          new CustomEvent(
            "orbitalai:playback-materialized",
            {
              detail: {
                objectIds:
                  materializedObjectIds,
              },
            },
          ),
        );



        const start =
          Cesium
            .JulianDate
            .fromIso8601(
              playback.start
            );

        const stop =
          Cesium
            .JulianDate
            .fromIso8601(
              playback.end
            );


        viewer.clock.startTime =
          start.clone();

        viewer.clock.stopTime =
          stop.clone();

        viewer.clock.currentTime =
          start.clone();


        viewer.clock.clockRange =
          Cesium
            .ClockRange
            .CLAMPED;

        viewer.clock.clockStep =
          Cesium
            .ClockStep
            .SYSTEM_CLOCK_MULTIPLIER;




        reportClockTime(
          playback.start
        );


        let lastReportAt =
          0;


        removeTickListener =
          viewer
            .clock
            .onTick
            .addEventListener(
              clock => {
                const now =
                  performance.now();


                if (
                  now
                  - lastReportAt
                  >= 100
                ) {
                  lastReportAt =
                    now;


                  reportClockTime(
                    Cesium
                      .JulianDate
                      .toIso8601(
                        clock
                          .currentTime,
                        0,
                      )
                  );
                }


                if (
                  Cesium
                    .JulianDate
                    .greaterThanOrEquals(
                      clock.currentTime,
                      clock.stopTime,
                    )
                  && clock
                    .shouldAnimate
                ) {
                  clock.shouldAnimate =
                    false;


                  reportClockTime(
                    playback.end
                  );


                  setIsPlaying(
                    false
                  );
                }
              }
            );
      }
    );


    return () => {
      cancelled =
        true;

      removeTickListener?.();


      /*
       * Remove only entities created by
       * this playback effect. Snapshot
       * entities remain owned by the
       * normal globe lifecycle.
       */
      for (
        const objectId
        of temporaryPlaybackEntityIds
      ) {
        viewer.entities.removeById(
          `orbital-object-${objectId}`
        );
      }
    };

  }, [
    playback,
    ready,
    reportClockTime,
    setIsPlaying,
  ]);


  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !playback
    ) {
      return;
    }


    viewer.clock
      .shouldAnimate =
      isPlaying;

  }, [
    isPlaying,
    playback,
    ready,
  ]);


  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !playback
    ) {
      return;
    }


    viewer.clock.multiplier =
      speed;

  }, [
    speed,
    playback,
    ready,
  ]);


  /*
   * Dynamic selected-object trajectories.
   *
   * PathGraphics follows the same
   * SampledPositionProperty used to
   * animate each orbital object.
   *
   * No orbit is calculated here:
   * all samples originate from the
   * deterministic backend playback.
   */
  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !playback
    ) {
      return;
    }


    let cancelled =
      false;


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          cancelled
          || viewer.isDestroyed()
        ) {
          return;
        }


        const palette = [
          "#55d6ef",
          "#f1c75b",
          "#9b8cff",
          "#63df9e",
          "#ef8c55",
          "#e977c6",
        ];


        /*
         * Remove any legacy static
         * trajectory entities that may
         * still exist from the previous
         * implementation.
         */
        for (
          const entity
          of [
            ...viewer.entities.values
          ]
        ) {
          if (
            entity.id.startsWith(
              "trajectory-"
            )
          ) {
            viewer.entities.remove(
              entity
            );
          }
        }


        for (
          const entity
          of viewer.entities.values
        ) {
          if (
            !entity.id.startsWith(
              "orbital-object-"
            )
          ) {
            continue;
          }


          const objectId =
            Number(
              entity.id.replace(
                "orbital-object-",
                ""
              )
            );


          const selected =
            selectedIds.includes(
              objectId
            );


          if (!selected) {
            entity.path =
              undefined;

            continue;
          }


          const color =
            Cesium.Color
              .fromCssColorString(
                palette[
                  objectId
                  % palette.length
                ]
              )
              .withAlpha(
                0.88
              );


          entity.path =
            new Cesium.PathGraphics({
              show:
                layers
                  .trajectories,

              /*
               * One hour behind the
               * current simulation time.
               */
              trailTime:
                3600,

              /*
               * One hour ahead.
               */
              leadTime:
                3600,

              width:
                2.4,

              resolution:
                30,

              material:
                color,
            });
        }
      }
    );


    return () => {
      cancelled =
        true;
    };

  }, [
    layers.trajectories,
    playback,
    ready,
    selectedIds,
  ]);


  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !seekRequest
    ) {
      return;
    }


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          viewer.isDestroyed()
        ) {
          return;
        }


        viewer.clock.currentTime =
          Cesium
            .JulianDate
            .fromIso8601(
              seekRequest.at
            );


        reportClockTime(
          seekRequest.at
        );
      }
    );

  }, [
    seekRequest,
    ready,
    reportClockTime,
  ]);


  /*
   * Conjunction visualization.
   *
   * TCA, miss distance and relative
   * velocity are authoritative backend
   * results.
   *
   * Cesium performs visualization-only
   * interpolation of backend-generated
   * playback samples.
   */
  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !playback
    ) {
      return;
    }


    let cancelled =
      false;


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          cancelled
          || viewer.isDestroyed()
        ) {
          return;
        }


        /*
         * Remove previous conjunction
         * visualization entities.
         */
        for (
          const entity
          of [
            ...viewer.entities.values
          ]
        ) {
          if (
            entity.id.startsWith(
              "conjunction-"
            )
          ) {
            viewer.entities.remove(
              entity
            );
          }
        }


        const playbackObjects =
          new Map(
            playback.objects.map(
              object => [
                object.object_id,
                object,
              ]
            )
          );


        function buildPosition(
          objectId: number
        ) {
          const object =
            playbackObjects.get(
              objectId
            );

          if (!object) {
            return null;
          }


          const property =
            new Cesium
              .SampledPositionProperty();


          for (
            const point
            of object.points
          ) {
            property.addSample(
              Cesium
                .JulianDate
                .fromIso8601(
                  point.at
                ),

              Cesium
                .Cartesian3
                .fromElements(
                  point.x_m,
                  point.y_m,
                  point.z_m,
                ),
            );
          }


          property
            .setInterpolationOptions({
              interpolationAlgorithm:
                Cesium
                  .LinearApproximation,

              interpolationDegree:
                1,
            });


          return property;
        }


        const start =
          new Date(
            playback.start
          ).getTime();

        const end =
          new Date(
            playback.end
          ).getTime();


        for (
          const event
          of conjunctionEvents
        ) {
          const tcaMs =
            new Date(
              event.tca
            ).getTime();


          if (
            !Number.isFinite(
              tcaMs
            )
            || tcaMs < start
            || tcaMs > end
          ) {
            continue;
          }


          const primary =
            buildPosition(
              event
                .primary_object_id
            );

          const secondary =
            buildPosition(
              event
                .secondary_object_id
            );


          if (
            !primary
            || !secondary
          ) {
            continue;
          }


          const tca =
            Cesium
              .JulianDate
              .fromIso8601(
                event.tca
              );


          const primaryAtTca =
            primary.getValue(
              tca
            );

          const secondaryAtTca =
            secondary.getValue(
              tca
            );


          if (
            !primaryAtTca
            || !secondaryAtTca
          ) {
            continue;
          }


          const midpoint =
            Cesium
              .Cartesian3
              .midpoint(
                primaryAtTca,
                secondaryAtTca,
                new Cesium
                  .Cartesian3(),
              );


          /*
           * Event visualization appears
           * only around TCA so the globe
           * remains operationally useful.
           */
          const visibleStart =
            Cesium
              .JulianDate
              .addSeconds(
                tca,
                -300,
                new Cesium
                  .JulianDate(),
              );

          const visibleStop =
            Cesium
              .JulianDate
              .addSeconds(
                tca,
                300,
                new Cesium
                  .JulianDate(),
              );


          const availability =
            new Cesium
              .TimeIntervalCollection([
                new Cesium
                  .TimeInterval({
                    start:
                      visibleStart,

                    stop:
                      visibleStop,
                  }),
              ]);


          viewer.entities.add({
            id:
              `conjunction-link-${event.id}`,

            availability,

            show:
              layers
                .conjunctions,

            polyline: {
              positions: [
                primaryAtTca,
                secondaryAtTca,
              ],

              width:
                2.5,

              material:
                Cesium.Color
                  .ORANGERED
                  .withAlpha(
                    0.92
                  ),
            },
          });


          viewer.entities.add({
            id:
              `conjunction-marker-${event.id}`,

            availability,

            position:
              midpoint,

            show:
              layers
                .conjunctions,

            point: {
              pixelSize:
                10,

              color:
                Cesium.Color
                  .ORANGERED,

              outlineColor:
                Cesium.Color
                  .WHITE,

              outlineWidth:
                1.5,
            },

            label: {
              text:
                `TCA\n${event.miss_distance_km.toFixed(3)} km`,

              font:
                "10px monospace",

              fillColor:
                Cesium.Color
                  .WHITE,

              outlineColor:
                Cesium.Color
                  .BLACK,

              outlineWidth:
                3,

              style:
                Cesium
                  .LabelStyle
                  .FILL_AND_OUTLINE,

              pixelOffset:
                new Cesium
                  .Cartesian2(
                    0,
                    -24,
                  ),

              showBackground:
                true,

              backgroundColor:
                Cesium.Color
                  .BLACK
                  .withAlpha(
                    0.62
                  ),
            },
          });
        }
      }
    );


    return () => {
      cancelled =
        true;
    };

  }, [
    conjunctionEvents,
    layers.conjunctions,
    playback,
    ready,
  ]);


  /*
   * Operational conjunction focus.
   *
   * The camera is framed around the
   * authoritative backend TCA positions
   * of both objects.
   */
  useEffect(() => {
    const viewer =
      viewerRef.current;


    if (
      !ready
      || !viewer
      || viewer.isDestroyed()
      || !activeConjunctionEventId
    ) {
      return;
    }


    const event =
      conjunctionEvents.find(
        candidate =>
          candidate.id
          === activeConjunctionEventId
      );


    if (!event) {
      return;
    }


    let cancelled =
      false;


    void import(
      "cesium"
    ).then(
      Cesium => {
        if (
          cancelled
          || viewer.isDestroyed()
        ) {
          return;
        }


        const primary =
          viewer.entities.getById(
            `orbital-object-${event.primary_object_id}`
          );

        const secondary =
          viewer.entities.getById(
            `orbital-object-${event.secondary_object_id}`
          );


        if (
          !primary?.position
          || !secondary?.position
        ) {
          return;
        }


        const tca =
          Cesium
            .JulianDate
            .fromIso8601(
              event.tca
            );


        const primaryPosition =
          primary.position.getValue(
            tca
          );

        const secondaryPosition =
          secondary.position.getValue(
            tca
          );


        if (
          !primaryPosition
          || !secondaryPosition
        ) {
          return;
        }


        viewer.trackedEntity =
          undefined;

        cameraLockedRef.current =
          false;

        setCameraLocked(
          false
        );


        const sphere =
          Cesium
            .BoundingSphere
            .fromPoints([
              primaryPosition,
              secondaryPosition,
            ]);


        const range =
          Math.max(
            sphere.radius
            * 25,
            800_000,
          );


        viewer.camera
          .flyToBoundingSphere(
            sphere,
            {
              duration:
                1.2,

              offset:
                new Cesium
                  .HeadingPitchRange(
                    0,
                    -0.45,
                    range,
                  ),
            },
          );
      }
    );


    return () => {
      cancelled =
        true;
    };

  }, [
    activeConjunctionEventId,
    conjunctionEvents,
    ready,
  ]);


  async function resetCamera() {
    const viewer =
      viewerRef.current;


    if (!viewer) {
      return;
    }


    const Cesium =
      await import(
        "cesium"
      );


    viewer.trackedEntity =
      undefined;


    cameraLockedRef.current =
      false;

    setCameraLocked(
      false
    );


    viewer.camera.flyTo({
      destination:
        Cesium.Cartesian3
          .fromDegrees(
            8.0,
            20.0,
            22_000_000,
          ),

      duration: 1.0,
    });
  }


  const selectedObjects =
    selectedIds
      .map(
        id =>
          snapshot
            ?.objects
            .find(
              object =>
                object.object_id
                === id,
            )
          ?? null,
      )
      .filter(
        (
          object,
        ): object is VisualizationObject =>
          object !== null,
      );


  const activeObject =
    activeObjectId === null
      ? null
      : snapshot
          ?.objects
          .find(
            object =>
              object.object_id
              === activeObjectId,
          )
        ?? null;


  return (
    <div className="orbitalGlobe">

      <div
        ref={containerRef}
        className="cesiumHost"
      />


      <div
        className="orbitalObjectLegend"
      >
        <button
          className="orbitalObjectLegendToggle"
          type="button"
          aria-expanded={legendOpen}
          aria-controls="orbital-object-legend-panel"
          onClick={() =>
            setLegendOpen(
              current => !current
            )
          }
        >
          <span>
            OBJECT LEGEND
          </span>

          <span
            aria-hidden="true"
          >
            {
              legendOpen
                ? "−"
                : "+"
            }
          </span>
        </button>

        {
          legendOpen
          && (
            <div
              id="orbital-object-legend-panel"
              className="orbitalObjectLegendPanel"
              aria-label="Orbital object legend"
            >
              <div
                className="orbitalObjectLegendTitle"
              >
                ORBITAL OBJECTS
              </div>

              {
                objectLegend.map(
                  item => (
                    <div
                      className="orbitalObjectLegendRow"
                      key={item.kind}
                    >
                      <span
                        className="orbitalObjectLegendDot"
                        style={{
                          backgroundColor:
                            item.color,
                        }}
                      />

                      <span
                        className="orbitalObjectLegendLabel"
                      >
                        {item.label}
                      </span>

                      <span
                        className="orbitalObjectLegendCount"
                      >
                        {
                          item.count
                            .toLocaleString()
                        }
                      </span>
                    </div>
                  )
                )
              }
            </div>
          )
        }
      </div>


      {!ready && (
        <div className="globeLoading">
          <div className="loadingRing" />

          <span>
            INITIALIZING ORBITAL VIEW
          </span>
        </div>
      )}


      <div className="globeToolbar">

        <button
          onClick={() =>
            toggleCameraLockRef
              .current()
          }
          type="button"
        >
          {
            cameraLocked
              ? "UNLOCK TARGET"
              : "LOCK TARGET"
          }
        </button>


        <button
          onClick={
            resetCamera
          }
          type="button"
        >
          GLOBAL VIEW
        </button>


        <button
          disabled={
            selectedIds.length
            === 0
          }
          onClick={() =>
            setIsolateSelection(
              current =>
                !current
            )
          }
          type="button"
        >
          {
            isolateSelection
              ? "SHOW ALL OBJECTS"
              : "ISOLATE SELECTION"
          }
        </button>


        <button
          disabled={
            selectedIds.length
            === 0
          }
          onClick={() =>
            clearSelectionRef
              .current()
          }
          type="button"
        >
          CLEAR SELECTION
        </button>

      </div>


      {
        selectedObjects.length
        > 0
        && (
          <div className="selectionPanel">

            <div className="selectionTitle">
              SELECTED OBJECTS

              <strong>
                {
                  selectedObjects.length
                }
              </strong>
            </div>


            <div className="selectionList">

              {
                selectedObjects.map(
                  object => (
                    <div
                      className={
                        object.object_id
                        === activeObjectId
                          ? "selectionRow active"
                          : "selectionRow"
                      }
                      key={
                        object.object_id
                      }
                    >

                      <button
                        className="selectionFocus"
                        onClick={() =>
                          focusObjectRef
                            .current(
                              object.object_id,
                            )
                        }
                        type="button"
                      >
                        <span>
                          {
                            object.object_name
                          }
                        </span>

                        <small>
                          NORAD{" "}
                          {
                            object.norad_cat_id
                          }
                        </small>
                      </button>


                      <button
                        className="selectionRemove"
                        onClick={() =>
                          removeSelectionRef
                            .current(
                              object.object_id,
                            )
                        }
                        type="button"
                      >
                        ×
                      </button>

                    </div>
                  ),
                )
              }

            </div>

          </div>
        )
      }


      {
        activeObject
        && (
          <div className="objectInspector">

            <div className="inspectorHeader">
              <div>
                <span>
                  ACTIVE TARGET
                </span>

                <strong>
                  {
                    activeObject
                      .object_name
                  }
                </strong>
              </div>

              <div className="noradBadge">
                NORAD{" "}
                {
                  activeObject
                    .norad_cat_id
                }
              </div>
            </div>


            <div className="inspectorGrid">


              <div>
                <span>
                  OWNER
                </span>

                <strong>
                  {
                    activeObject
                      .owner
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>


              <div>
                <span>
                  OPERATIONAL STATUS
                </span>

                <strong>
                  {
                    formatOperationalStatus(
                      activeObject
                        .ops_status_code
                    )
                  }
                </strong>
              </div>


              <div>
                <span>
                  LAUNCH DATE
                </span>

                <strong>
                  {
                    activeObject
                      .launch_date
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>


              <div>
                <span>
                  LAUNCH SITE
                </span>

                <strong>
                  {
                    activeObject
                      .launch_site
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>

              <div>
                <span>
                  TYPE
                </span>

                <strong>
                  {
                    activeObject
                      .object_type
                    ?? "UNKNOWN"
                  }
                </strong>
              </div>


              <div>
                <span>
                  EPHEMERIS
                </span>

                <strong>
                  {
                    activeObject
                      .ephemeris_status
                  }
                </strong>
              </div>


              <div>
                <span>
                  SPEED
                </span>

                <strong>
                  {
                    velocityKmS(
                      activeObject
                    ).toFixed(
                      3
                    )
                  }{" "}
                  km/s
                </strong>
              </div>


              <div>
                <span>
                  ALTITUDE
                </span>

                <strong>
                  ~
                  {
                    approximateAltitudeKm(
                      activeObject
                    ).toFixed(
                      0
                    )
                  }{" "}
                  km
                </strong>
              </div>

            </div>


            <div className="inspectorEpoch">
              <span>
                ELEMENT EPOCH
              </span>

              <strong>
                {
                  new Date(
                    activeObject
                      .epoch
                  ).toISOString()
                }
              </strong>
            </div>


            {
              loadingIds.length
              > 0
              && (
                <div className="trajectoryStatus">
                  PROPAGATING{" "}
                  {
                    loadingIds.length
                  }{" "}
                  TRAJECTORY
                  {
                    loadingIds.length
                    === 1
                      ? ""
                      : "IES"
                  }…
                </div>
              )
            }


            {
              trajectoryError
              && (
                <div className="trajectoryError">
                  {
                    trajectoryError
                  }
                </div>
              )
            }

          </div>
        )
      }


      <div className="globeLegend">

        <span>
          {
            snapshot
              ? `${snapshot.rendered_objects} OBJECTS`
              : "NO OBJECT DATA"
          }
        </span>

        <span className="separator">
          /
        </span>

        <span>
          {
            selectedIds.length
          }{" "}
          SELECTED
        </span>

        <span className="separator">
          /
        </span>

        <span>
          ITRS / ECEF
        </span>

      </div>

    </div>
  );
}
