"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  useOrbitalView,
} from "@/components/globe/orbital-view-context";

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
}: OrbitalGlobeProps) {
  const {
    layers,
    viewMode,
    imageryMode,
  } = useOrbitalView();
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


      async function loadTrajectory(
        object:
          VisualizationObject,
      ) {
        setLoadingIds(
          current =>
            current.includes(
              object.object_id
            )
              ? current
              : [
                  ...current,
                  object.object_id,
                ],
        );


        setTrajectoryError(
          null,
        );


        try {
          const start =
            snapshot?.at
            ?? new Date()
              .toISOString();


          const endDate =
            new Date(
              start
            );


          endDate.setUTCHours(
            endDate.getUTCHours()
            + 2,
          );


          const params =
            new URLSearchParams({
              start,

              end:
                endDate
                  .toISOString(),

              step_seconds:
                "60",
            });


          const response =
            await fetch(
              `/api/visualization/objects/${object.object_id}/trajectory?${params}`,
              {
                cache:
                  "no-store",
              },
            );


          if (!response.ok) {
            throw new Error(
              `Trajectory request failed (${response.status})`,
            );
          }


          const trajectory =
            (await response.json()) as ObjectTrajectory;


          if (
            disposed
            || viewer.isDestroyed()
          ) {
            return;
          }


          viewer.entities.removeById(
            `trajectory-${object.object_id}`,
          );


          const positions =
            trajectory.points.map(
              point =>
                Cesium
                  .Cartesian3
                  .fromElements(
                    point.x_m,
                    point.y_m,
                    point.z_m,
                  ),
            );


          viewer.entities.add({
            id:
              `trajectory-${object.object_id}`,

            name:
              `${trajectory.object_name} trajectory`,

            show:
              layersRef.current
                .trajectories,

            polyline: {
              positions,

              width: 2.5,

              arcType:
                Cesium
                  .ArcType
                  .NONE,

              material:
                trajectoryColor(
                  object.object_id,
                )
                  .withAlpha(
                    0.9,
                  ),
            },
          });

        } catch (error) {
          setTrajectoryError(
            error instanceof Error
              ? error.message
              : "Trajectory loading failed",
          );

        } finally {
          setLoadingIds(
            current =>
              current.filter(
                id =>
                  id
                  !== object.object_id,
              ),
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


          void loadTrajectory(
            object
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
