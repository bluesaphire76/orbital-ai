"use client";

import {
  createContext,
  useContext,
  useState,
} from "react";


interface ConjunctionFocusContextValue {
  activeEventId:
    number | null;

  setActiveEventId:
    React.Dispatch<
      React.SetStateAction<
        number | null
      >
    >;
}


const ConjunctionFocusContext =
  createContext<
    ConjunctionFocusContextValue
    | null
  >(null);


export function ConjunctionFocusProvider({
  children,
}: {
  children:
    React.ReactNode;
}) {
  const [
    activeEventId,
    setActiveEventId,
  ] = useState<
    number | null
  >(null);


  return (
    <ConjunctionFocusContext.Provider
      value={{
        activeEventId,
        setActiveEventId,
      }}
    >
      {children}
    </ConjunctionFocusContext.Provider>
  );
}


export function useConjunctionFocus() {
  const context =
    useContext(
      ConjunctionFocusContext
    );


  if (!context) {
    throw new Error(
      "useConjunctionFocus must be used inside ConjunctionFocusProvider"
    );
  }


  return context;
}
