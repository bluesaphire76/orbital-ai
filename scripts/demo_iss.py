from datetime import datetime, timezone

from sgp4.conveniences import sat_epoch_datetime

from ingestion.celestrak import fetch_gp_by_catnr
from orbital_engine.propagation import propagate_utc, satrec_from_omm


ISS_NORAD_ID = 25544


def main() -> None:
    records, from_cache = fetch_gp_by_catnr(ISS_NORAD_ID)

    record = records[0]
    satellite = satrec_from_omm(record)

    now = datetime.now(timezone.utc)

    position, velocity = propagate_utc(satellite, now)

    print()
    print("OrbitalAI v0.1 - SGP4 propagation")
    print("--------------------------------")
    print(f"Object       : {record['OBJECT_NAME']}")
    print(f"NORAD CAT ID : {record['NORAD_CAT_ID']}")
    print(f"Object ID    : {record.get('OBJECT_ID')}")
    print(f"Element epoch: {sat_epoch_datetime(satellite).isoformat()}")
    print(f"Propagation  : {now.isoformat()}")
    print(f"Data source  : {'local cache' if from_cache else 'CelesTrak'}")

    print()
    print("TEME position [km]")
    print(f"  X: {position[0]:12.3f}")
    print(f"  Y: {position[1]:12.3f}")
    print(f"  Z: {position[2]:12.3f}")

    print()
    print("TEME velocity [km/s]")
    print(f"  VX: {velocity[0]:10.6f}")
    print(f"  VY: {velocity[1]:10.6f}")
    print(f"  VZ: {velocity[2]:10.6f}")


if __name__ == "__main__":
    main()
