from django.db import migrations

def initial_plan(apps, schema_editor):
    apps.get_model('portal', 'Plan').objects.get_or_create(name='三天体验')

class Migration(migrations.Migration):
    dependencies = [('portal','0002_plan_pass_hours_pass_price_pass_title_and_more')]
    operations = [migrations.RunPython(initial_plan,migrations.RunPython.noop)]
