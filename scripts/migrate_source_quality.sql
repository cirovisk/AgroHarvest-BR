BEGIN;

ALTER TABLE fato_risco_zarc
    ADD COLUMN IF NOT EXISTS safra VARCHAR(20) NOT NULL DEFAULT 'nao-informada',
    ADD COLUMN IF NOT EXISTS finalidade VARCHAR NOT NULL DEFAULT 'nao-informada',
    ADD COLUMN IF NOT EXISTS cod_cultura_zarc VARCHAR;

DROP INDEX IF EXISTS ix_fato_risco_zarc_cod_cultura_zarc;
CREATE INDEX ix_fato_risco_zarc_cod_cultura_zarc
    ON fato_risco_zarc (cod_cultura_zarc);

ALTER TABLE fato_risco_zarc DROP CONSTRAINT IF EXISTS _zarc_uc;
ALTER TABLE fato_risco_zarc
    ADD CONSTRAINT _zarc_uc UNIQUE
    (id_cultura, id_municipio, tipo_solo, periodo_plantio, safra, finalidade);

ALTER TABLE fato_sigef_reserva_semente
    ADD COLUMN IF NOT EXISTS data_plantio TIMESTAMP,
    ADD COLUMN IF NOT EXISTS quantidade_reservada_t DOUBLE PRECISION;

COMMIT;
