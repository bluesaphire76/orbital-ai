import type {
  ConjunctionEvent,
  ConjunctionRun,
} from "@/types/conjunction";

import type {
  VisualizationSnapshot,
} from "@/types/visualization";


const API_URL =
  process.env.ORBITAL_API_URL ??
  "http://127.0.0.1:8008";


async function request<T>(
  path: string,
): Promise<T> {
  const response = await fetch(
    `${API_URL}${path}`,
    {
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error(
      `OrbitalAI API returned ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}


export function getLatestConjunctionRun() {
  return request<ConjunctionRun>(
    "/conjunctions/runs/latest",
  );
}


export function getConjunctionEvents(
  runId: number,
) {
  return request<ConjunctionEvent[]>(
    `/conjunctions/runs/${runId}/events`,
  );
}


export function getVisualizationSnapshot(
  at?: string,
) {
  const query =
    at
      ? `?at=${encodeURIComponent(at)}`
      : "";

  return request<VisualizationSnapshot>(
    `/visualization/snapshot${query}`,
  );
}
