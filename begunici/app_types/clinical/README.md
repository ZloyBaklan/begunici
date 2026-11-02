# Clinical treatment

The independent clinical journal is available at `/animals/treatment/` and from
the veterinary navigation. Animal assignment and analytics link to its history.
Episodes use the stable Tag identity, preserving history through retagging and
animal type conversion. Ordinary veterinary treatments keep their existing
immediate stock accounting.

Clinical doses accumulate in the diary. Final consumption is confirmed once on
discharge. Insufficient stock leaves a draft expense for reconciliation without
preventing medical discharge; retries cannot charge stock twice.

Admin, vet and zootech manage treatment. Main can admit animals and read history;
finans can read history. Admission of archived animals is forbidden. An open
episode must be completed before removing treatment or archiving the animal.

Schema: `animals/0044_animal_treatment` follows the existing breeding draft
migration `0043_lambing_group_drafts`; `clinical/0001_initial` depends on 0044.
No legacy animals are automatically assigned treatment.

Tests live in the shared `begunici/tests` directory:

```sh
python manage.py test begunici.tests.test_clinical_workflow begunici.tests.test_clinical_concurrency begunici.tests.test_clinical_integration
```

These tests use the ordinary project settings and migrations. No alternative
migration runner or production migration bypass is required.
