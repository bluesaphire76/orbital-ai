"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  MouseEvent,
} from "react";

import type {
  VisualizationObject,
} from "@/types/visualization";


const MAX_RESULTS = 12;


export function OrbitalCatalogSearch() {
  const [
    objects,
    setObjects,
  ] = useState<
    VisualizationObject[]
  >([]);

  const [
    query,
    setQuery,
  ] = useState("");

  const [
    open,
    setOpen,
  ] = useState(false);


  useEffect(() => {
    function handleCatalogAvailable(
      event: Event,
    ) {
      const customEvent =
        event as CustomEvent<{
          objects:
            VisualizationObject[];
        }>;


      setObjects(
        customEvent.detail
          ?.objects
        ?? []
      );
    }


    window.addEventListener(
      "orbitalai:catalog-available",
      handleCatalogAvailable,
    );


    window.dispatchEvent(
      new CustomEvent(
        "orbitalai:catalog-request"
      )
    );


    return () => {
      window.removeEventListener(
        "orbitalai:catalog-available",
        handleCatalogAvailable,
      );
    };

  }, []);


  const results =
    useMemo(
      () => {
        const normalized =
          query
            .trim()
            .toUpperCase();


        if (
          normalized.length < 2
        ) {
          return [];
        }


        const exact:
          VisualizationObject[] = [];

        const starts:
          VisualizationObject[] = [];

        const contains:
          VisualizationObject[] = [];


        for (
          const object
          of objects
        ) {
          const name =
            object.object_name
              .toUpperCase();

          const norad =
            String(
              object.norad_cat_id
            );


          if (
            norad === normalized
          ) {
            exact.push(
              object
            );

            continue;
          }


          if (
            name.startsWith(
              normalized
            )
            || norad.startsWith(
              normalized
            )
          ) {
            starts.push(
              object
            );

            continue;
          }


          if (
            name.includes(
              normalized
            )
          ) {
            contains.push(
              object
            );
          }
        }


        return [
          ...exact,
          ...starts,
          ...contains,
        ].slice(
          0,
          MAX_RESULTS
        );
      },
      [
        objects,
        query,
      ],
    );


  function selectResult(
    event:
      MouseEvent<HTMLButtonElement>,
    object:
      VisualizationObject,
  ) {
    const additive =
      event.shiftKey
      || event.ctrlKey
      || event.metaKey;


    window.dispatchEvent(
      new CustomEvent(
        "orbitalai:select-object",
        {
          detail: {
            objectId:
              object.object_id,

            additive,
          },
        },
      ),
    );


    setQuery(
      object.object_name
    );

    setOpen(
      false
    );
  }


  return (
    <section className="workspaceRailSection catalogSearchSection">

      <div className="workspaceSectionHeader">
        <div>
          <span className="sectionLabel">
            CATALOG SEARCH
          </span>

          <strong>
            Find orbital object
          </strong>
        </div>

        <span className="catalogSearchCount">
          {
            objects.length
              > 0
              ? objects.length
                  .toLocaleString()
              : "—"
          }
        </span>
      </div>


      <div className="catalogSearch">

        <input
          aria-label="Search orbital catalog"
          autoComplete="off"
          className="catalogSearchInput"
          onChange={
            event => {
              setQuery(
                event.target.value
              );

              setOpen(
                true
              );
            }
          }
          onFocus={() =>
            setOpen(
              true
            )
          }
          placeholder="ISS, 25544, STARLINK..."
          type="search"
          value={
            query
          }
        />


        {
          open
          && query
              .trim()
              .length >= 2
          && (
            <div className="catalogSearchResults">

              {
                results.length > 0
                  ? results.map(
                      object => (
                        <button
                          className="catalogSearchResult"
                          key={
                            object.object_id
                          }
                          onClick={
                            event =>
                              selectResult(
                                event,
                                object,
                              )
                          }
                          type="button"
                        >
                          <span>
                            <strong>
                              {
                                object.object_name
                              }
                            </strong>

                            <small>
                              {
                                object.object_type
                                ?? "OBJECT"
                              }
                            </small>
                          </span>

                          <em>
                            NORAD{" "}
                            {
                              object.norad_cat_id
                            }
                          </em>
                        </button>
                      )
                    )
                  : (
                      <div className="catalogSearchEmpty">
                        NO MATCHING OBJECTS
                      </div>
                    )
              }

            </div>
          )
        }


        <small className="catalogSearchHint">
          Ctrl / Cmd / Shift + click to add to selection
        </small>

      </div>

    </section>
  );
}
