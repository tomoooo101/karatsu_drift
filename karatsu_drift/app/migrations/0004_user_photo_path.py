from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_vehicle_photo_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="photo_path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
