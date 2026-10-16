from django.db import migrations


def seed_one_way_lighting(apps, schema_editor):
    ElectricalExercise = apps.get_model("electrical_lab", "ElectricalExercise")
    ElectricalExercise.objects.using(schema_editor.connection.alias).get_or_create(
        slug="one-way-lighting",
        defaults={
            "title": "Build a 1-Way Lighting Circuit",
            "description": "Connect the supply, MCB, one-way switch, and lamp. Check live, neutral, and earth before energizing.",
            "voltage": 230,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("electrical_lab", "0001_initial")]

    operations = [migrations.RunPython(seed_one_way_lighting, migrations.RunPython.noop)]
