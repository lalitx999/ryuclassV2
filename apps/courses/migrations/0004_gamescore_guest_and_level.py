import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('courses', '0003_ryutube')]

    operations = [
        migrations.AlterField(
            model_name='gamescore', name='user',
            field=models.ForeignKey(blank=True, db_column='user_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='game_scores', to='users.user'),
        ),
        migrations.AddField(model_name='gamescore', name='player_name', field=models.CharField(blank=True, default='', max_length=50)),
        migrations.AddField(model_name='gamescore', name='jlpt_level', field=models.CharField(default='N5', max_length=2)),
    ]
