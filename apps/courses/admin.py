from django.contrib import admin
from django.contrib import messages
from .models import Course, Module, Lesson, Enrollment, Progress, Note, GameScore
from .emails import send_course_renewal_reminder_email

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
    actions = ['send_renewal_reminder_action']

    @admin.action(description="📧 ส่งอีเมลเตือนต่ออายุคอร์สเรียน (Renewal Reminder)")
    def send_renewal_reminder_action(self, request, queryset):
        success_count = 0
        fail_count = 0
        for enrollment in queryset:
            if enrollment.is_lifetime_video:
                continue
            ok = send_course_renewal_reminder_email(enrollment)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        
        if success_count > 0:
            self.message_user(
                request, 
                f"ส่งอีเมลเตือนต่ออายุสำเร็จ {success_count} รายการ", 
                level=messages.SUCCESS
            )
        if fail_count > 0:
            self.message_user(
                request, 
                f"ส่งอีเมลล้มเหลว {fail_count} รายการ", 
                level=messages.ERROR
            )

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
