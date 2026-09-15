export interface ConjunctionRun {
  id: number;
  source: string;

  window_start: string;
  window_end: string;

  step_seconds: number;
  candidate_distance_km: number;

  objects: number;
  samples: number;

  propagation_attempts: number;
  propagation_failures: number;
  expired_skips: number;

  shared_solution_groups: number;
  shared_solution_objects: number;
  suppressed_shared_pairs: number;

  raw_candidates: number;
  unique_candidates: number;

  refinement_attempts: number;
  refinement_failures: number;

  event_count: number;
  duration_ms: number;

  started_at: string;
  completed_at: string;
}

export interface ConjunctionEvent {
  id: number;
  run_id: number;

  primary_object_id: number;
  primary_norad_cat_id: number;
  primary_name: string;

  secondary_object_id: number;
  secondary_norad_cat_id: number;
  secondary_name: string;

  tca: string;

  miss_distance_km: number;
  relative_velocity_km_s: number;

  method: string;
}
