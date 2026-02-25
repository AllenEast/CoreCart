from django.db import migrations, models


def empty_phone_to_null(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(phone="").update(phone=None)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.RunPython(empty_phone_to_null, migrations.RunPython.noop),
    ]
