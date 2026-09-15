export interface VisualizationObject {
  object_id: number;
  norad_cat_id: number;
  object_name: string;
  object_type: string | null;

  epoch: string;
  ephemeris_status: string;

  x_m: number;
  y_m: number;
  z_m: number;

  vx_m_s: number;
  vy_m_s: number;
  vz_m_s: number;
}

export interface VisualizationSnapshot {
  at: string;
  frame: string;

  objects: VisualizationObject[];

  total_elements: number;
  rendered_objects: number;
  expired_skips: number;
  propagation_failures: number;
}

export interface TrajectoryPoint {
  at: string;

  x_m: number;
  y_m: number;
  z_m: number;
}

export interface ObjectTrajectory {
  object_id: number;
  norad_cat_id: number;
  object_name: string;

  frame: string;

  start: string;
  end: string;
  step_seconds: number;

  points: TrajectoryPoint[];
}
