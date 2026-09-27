from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

class Course(models.Model):
    id = models.AutoField(primary_key=True) # Explicit ID mapping (1-5 for N5-N1)
    title = models.CharField(max_length=200)
    slug = models.CharField(max_length=220)
    description = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    price = models.DecimalField('ราคารายเดือน (30 วัน)', max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(Decimal('0.01'))])
    price_180 = models.DecimalField('ราคา 6 เดือน (180 วัน)', max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))], help_text='เว้นว่างเพื่อปิดแพ็กเกจ')
    price_365 = models.DecimalField('ราคา 1 ปี (365 วัน)', max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))], help_text='เว้นว่างเพื่อปิดแพ็กเกจ')
    price_lifetime = models.DecimalField('ราคาตลอดชีพ', max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))], help_text='เว้นว่างเพื่อปิดแพ็กเกจ')
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

def ensure_notes_table_exists():
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    lesson_id INT NOT NULL,
                    content LONGTEXT,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                    UNIQUE KEY user_lesson_unique (user_id, lesson_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    except Exception:
        pass

def ensure_game_scores_table_exists():
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_scores (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NULL,
                    player_name VARCHAR(50) NOT NULL DEFAULT '',
                    game_mode VARCHAR(50) NOT NULL DEFAULT 'kana',
                    jlpt_level VARCHAR(2) NOT NULL DEFAULT 'N5',
                    score INT NOT NULL DEFAULT 0,
                    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    except Exception:
        pass

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

