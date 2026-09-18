from django.contrib import admin
from .models import Course, Module, Lesson, Enrollment, Progress, Note, GameScore

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'is_active', 'sort_order')
    list_display_links = ('id', 'title')
    list_filter = ('is_active',)
    search_fields = ('title', 'slug')

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'course', 'sort_order', 'is_active')
    list_filter = ('course', 'is_active')
    search_fields = ('title',)

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'course', 'module', 'is_free', 'is_active', 'sort_order')
    list_filter = ('course', 'module', 'is_free', 'is_active')
    search_fields = ('title',)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'course', 'status', 'is_active', 'is_lifetime_video', 'video_expires_at')
    list_filter = ('course', 'status', 'is_active', 'is_lifetime_video')
    search_fields = ('user__email', 'user__name', 'course__title')

@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'lesson', 'video_time', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'completed_at')
    search_fields = ('user__email', 'lesson__title')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'lesson', 'updated_at')
    search_fields = ('user__email', 'lesson__title', 'content')

@admin.register(GameScore)
class GameScoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'game_mode', 'score', 'created_at')
    list_filter = ('game_mode', 'created_at')
    search_fields = ('user__email', 'game_mode')
