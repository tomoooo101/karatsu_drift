from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_costrecord_ck_cost_amount_nonnegative_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="photo_path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
