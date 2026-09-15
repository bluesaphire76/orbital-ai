"use client";

import {
  useEffect,
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
        status: string,
      ) {
        switch (
          status.toUpperCase()
        ) {
          case "FRESH":
            return Cesium.Color
              .fromCssColorString(
                "#56d9ef",
              );

          case "AGING":
            return Cesium.Color
              .fromCssColorString(
                "#f1c75b",
              );

          case "STALE":
            return Cesium.Color
              .fromCssColorString(
                "#ef8c55",
              );

          default:
            return Cesium.Color
              .WHITE;
        }
      }


      function trajectoryColor(
        objectId: number,
      ) {
        const palette = [
          "#55d6ef",
          "#f1c75b",
          "#9b8cff",
          "#63df9e",
          "#ef8c55",
          "#e977c6",
        ];

        return Cesium.Color
          .fromCssColorString(
            palette[
              objectId
              % palette.length
            ],
          );
      }


      if (snapshot) {
        for (
          const object
          of snapshot.objects
        ) {
          const color =
            objectColor(
              object.ephemeris_status,
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


      function clearSelection() {
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
          clearSelection();
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


      window.addEventListener(
        "keydown",
        handleKeyDown,
      );


      if (!disposed) {
        setReady(
          true
        );
      }


      return () => {
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
            if (entity.point) {
              entity.point.show =
                new Cesium
                  .ConstantProperty(
                    layers.objects
                  );
            }


            if (entity.label) {
              entity.label.show =
                new Cesium
                  .ConstantProperty(
                    layers.labels
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
    layers,
    ready,
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
     * Keep a stable non-null Viewer
     * reference for the async closure.
     */
    const activeViewer =
      viewer;


    let cancelled =
      false;


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


        for (
          const object
          of playback.objects
        ) {
          const entity =
            viewer.entities
              .getById(
                `orbital-object-${object.object_id}`
              );


          if (!entity) {
            continue;
          }


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
           * intentionally used here.
           * This is visualization only,
           * never an orbital calculation.
           */
          position
            .setInterpolationOptions({
              interpolationAlgorithm:
                Cesium
                  .LinearApproximation,

              interpolationDegree:
                1,
            });


          entity.position =
            position;
        }


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

        viewer.clock.multiplier =
          1;

        viewer.clock.shouldAnimate =
          false;


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
