-- One row per study with its reliability badges (ALCANCE.md §10).
select * from {{ ref('int_study_reliability') }}
