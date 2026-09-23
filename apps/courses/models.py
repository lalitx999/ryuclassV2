from django.db import models
from django.conf import settings

class Course(models.Model):
    id = models.AutoField(primary_key=True) # Explicit ID mapping (1-5 for N5-N1)
    title = models.CharField(max_length=200)
    slug = models.CharField(max_length=220)
    description = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    thumbnail = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses'

    def __str__(self):
        return f"{self.title} (ID: {self.id})"

class Module(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules', db_column='course_id')
    title = models.CharField(max_length=255)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'modules'

    def __str__(self):
        return f"{self.title} ({self.course.title})"

class Lesson(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons', db_column='course_id')
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='lessons', db_column='module_id')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    video_url = models.TextField(blank=True, null=True, help_text="AES-256 encrypted URL")
    duration = models.IntegerField(default=0, help_text="seconds")
    sort_order = models.IntegerField(default=0)
    is_free = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lessons'

    def __str__(self):
        return f"{self.title} ({self.course.title})"

class Enrollment(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments', db_column='user_id')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments', db_column='course_id')
    payment_id = models.PositiveIntegerField(blank=True, null=True, db_column='payment_id') # We can link this to Payment model later
    is_active = models.BooleanField(default=False)
    video_expires_at = models.DateField(blank=True, null=True)
    zoom_expires_at = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[('ACTIVE', 'Active'), ('EXPIRED', 'Expired'), ('BANNED', 'Banned')],
        default='ACTIVE'
    )
    is_lifetime_video = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'enrollments'

    def __str__(self):
        return f"User {self.user.email} -> Course {self.course.title} ({self.status})"

class Progress(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress_logs', db_column='user_id')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress_logs', db_column='lesson_id')
    completed_at = models.DateTimeField(auto_now_add=True)
    video_time = models.PositiveIntegerField(default=0, help_text="seconds played")
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'progress'

    def __str__(self):
        return f"User {self.user.email} -> Lesson {self.lesson.title} ({self.video_time}s)"

class Note(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='personal_notes', db_column='user_id')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='personal_notes', db_column='lesson_id')
    content = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notes'
        unique_together = ('user', 'lesson')

    def __str__(self):
        return f"Note: User {self.user.email} -> Lesson {self.lesson.title}"

class GameScore(models.Model):
    id = models.AutoField(primary_key=True)
    # Legacy user IDs are unsigned in the production MySQL schema.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_scores', db_column='user_id', null=True, blank=True, db_constraint=False)
    player_name = models.CharField(max_length=50, blank=True, default='')
    game_mode = models.CharField(max_length=50, default='kana')
    jlpt_level = models.CharField(max_length=2, default='N5')
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'game_scores'

    def __str__(self):
        name = self.user.email if self.user else self.player_name
        return f"Score {self.score} ({self.game_mode}/{self.jlpt_level}) by {name}"


class RyutubeCategory(models.Model):
    """A public, editorial category. It is deliberately separate from courses."""
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ryutube_categories'
        ordering = ('sort_order', 'name')
        verbose_name = 'หมวด Ryutube'
        verbose_name_plural = 'หมวด Ryutube'

    def __str__(self):
        return self.name


class RyutubeVideo(models.Model):
    """A publicly published video; it never grants access to a member course."""
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    description = models.TextField(blank=True, default='')
    video_url = models.TextField(help_text='YouTube URL or embed URL')
    thumbnail = models.CharField(max_length=500, blank=True, default='')
    category = models.ForeignKey(RyutubeCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='videos')
    # Legacy production databases use a different primary-key definition for courses.
    # Keep this optional editorial link without creating an incompatible DB-level FK.
    linked_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='ryutube_videos', db_constraint=False)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ryutube_videos'
        ordering = ('-published_at', 'sort_order', '-created_at')
        verbose_name = 'วิดีโอ Ryutube'
        verbose_name_plural = 'วิดีโอ Ryutube'

    def __str__(self):
        return self.title
