# Generated manually for the Ryutube public-video library.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('courses', '0002_gamescore_note')]

    operations = [
        migrations.CreateModel(
            name='RyutubeCategory',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('sort_order', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'db_table': 'ryutube_categories', 'ordering': ('sort_order', 'name'), 'verbose_name': 'หมวด Ryutube', 'verbose_name_plural': 'หมวด Ryutube'},
        ),
        migrations.CreateModel(
            name='RyutubeVideo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=280, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('video_url', models.TextField(help_text='YouTube URL or embed URL')),
                ('thumbnail', models.CharField(blank=True, default='', max_length=500)),
                ('is_published', models.BooleanField(default=False)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('sort_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='videos', to='courses.ryutubecategory')),
                ('linked_course', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ryutube_videos', to='courses.course')),
            ],
            options={'db_table': 'ryutube_videos', 'ordering': ('-published_at', 'sort_order', '-created_at'), 'verbose_name': 'วิดีโอ Ryutube', 'verbose_name_plural': 'วิดีโอ Ryutube'},
        ),
    ]
