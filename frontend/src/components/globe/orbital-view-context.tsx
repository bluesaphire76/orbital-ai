"use client";

import {
  createContext,
  useContext,
  useState,
} from "react";


export type CameraMode =
  | "orbit"
  | "pan";

export type ImageryMode =
  | "local"
  | "satellite";


export interface OrbitalLayers {
  objects: boolean;
  labels: boolean;
  trajectories: boolean;
  conjunctions: boolean;
}


interface OrbitalViewContextValue {
  layers: OrbitalLayers;

  setLayers:
    React.Dispatch<
      React.SetStateAction<
        OrbitalLayers
      >
    >;

  viewMode:
    CameraMode;

  setViewMode:
    React.Dispatch<
      React.SetStateAction<
        CameraMode
      >
    >;

  imageryMode:
    ImageryMode;

  setImageryMode:
    React.Dispatch<
      React.SetStateAction<
        ImageryMode
      >
    >;
}


const OrbitalViewContext =
  createContext<
    OrbitalViewContextValue
    | null
  >(
    null
  );


export function OrbitalViewProvider({
  children,
}: {
  children:
    React.ReactNode;
}) {
  const [
    layers,
    setLayers,
  ] = useState<OrbitalLayers>({
    objects: true,
    labels: true,
    trajectories: true,
    conjunctions: true,
  });


  const [
    viewMode,
    setViewMode,
  ] = useState<CameraMode>(
    "orbit"
  );


  /*
   * Satellite is the default visual
   * mode. Local remains available
   * as the offline fallback.
   */
  const [
    imageryMode,
    setImageryMode,
  ] = useState<ImageryMode>(
    "satellite"
  );


  return (
    <OrbitalViewContext.Provider
      value={{
        layers,
        setLayers,
        viewMode,
        setViewMode,
        imageryMode,
        setImageryMode,
      }}
    >
      {children}
    </OrbitalViewContext.Provider>
  );
}


export function useOrbitalView() {
  const context =
    useContext(
      OrbitalViewContext
    );


  if (!context) {
    throw new Error(
      "useOrbitalView must be used inside OrbitalViewProvider"
    );
  }


  return context;
}
