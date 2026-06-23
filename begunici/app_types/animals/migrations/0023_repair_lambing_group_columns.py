from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0022_archiveact"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE "animals_lambing"
                ADD COLUMN IF NOT EXISTS "completion_type" varchar(30) NOT NULL DEFAULT 'normal';

            ALTER TABLE "animals_lambing"
                ADD COLUMN IF NOT EXISTS "source_group_id" bigint NULL;

            CREATE INDEX IF NOT EXISTS "animals_lambing_completion_type_repair_idx"
                ON "animals_lambing" ("completion_type");

            CREATE INDEX IF NOT EXISTS "animals_lambing_source_group_id_repair_idx"
                ON "animals_lambing" ("source_group_id");

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'animals_lambing_source_group_id_repair_fk'
                ) THEN
                    ALTER TABLE "animals_lambing"
                        ADD CONSTRAINT "animals_lambing_source_group_id_repair_fk"
                        FOREIGN KEY ("source_group_id")
                        REFERENCES "animals_lambinggroup" ("id")
                        DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END
            $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
