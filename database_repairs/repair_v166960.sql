BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM stretches
        WHERE id = 1384
          AND bottom_manhole_id = 859
          AND bottom_connection_id = 16
          AND from_brond = '3242014'
          AND to_brond = '3243013'
    ) THEN
        RAISE EXCEPTION 'Stræk 1384 har ændret sig. Ingen rettelse udført.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM manholes
        WHERE id = 871
          AND manhole_no = '3243014'
    ) THEN
        RAISE EXCEPTION 'Den korrekte brønd 871 blev ikke fundet.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM deviations
        WHERE bottom_manhole_id = 859 OR top_manhole_id = 859
    ) OR EXISTS (
        SELECT 1 FROM vpmanhole_deliveries WHERE manhole_id = 859
    ) OR EXISTS (
        SELECT 1 FROM stretches
        WHERE id <> 1384
          AND (bottom_manhole_id = 859 OR top_manhole_id = 859)
    ) OR EXISTS (
        SELECT 1 FROM manhole_connections
        WHERE manhole_id = 859 AND id <> 16
    ) OR EXISTS (
        SELECT 1 FROM manhole_work
        WHERE manhole_id = 859 AND id <> 291
    ) THEN
        RAISE EXCEPTION 'Der findes yderligere referencer til brønd 859. Ingen rettelse udført.';
    END IF;
END
$$;

UPDATE stretches
SET bottom_manhole_id = 871,
    from_brond = '3243014'
WHERE id = 1384;

UPDATE manhole_connections
SET manhole_id = 871,
    updated_at = NOW()
WHERE id = 16
  AND manhole_id = 859;

DELETE FROM manhole_work
WHERE id = 291
  AND manhole_id = 859
  AND status = 'planned'
  AND source = 'c5_csv';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM manhole_work WHERE manhole_id = 859
    ) THEN
        RAISE EXCEPTION 'Brønd 859 har stadig arbejdsregistreringer.';
    END IF;
END
$$;

DELETE FROM manholes
WHERE id = 859
  AND manhole_no = '3242014';

COMMIT;

SELECT
    id,
    from_brond,
    to_brond,
    bottom_manhole_id,
    bottom_connection_id
FROM stretches
WHERE id = 1384;
