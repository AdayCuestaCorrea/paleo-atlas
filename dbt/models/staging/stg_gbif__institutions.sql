-- Institutions holding GBIF fossil specimens of the encyclopedia genera (monthly extract).
select *
from {{ read_optional_parquet('raw/gbif/extract/*/institutions.parquet', {
    'institution_code': 'varchar', 'specimens': 'bigint', 'genera': 'bigint'
}) }}
