from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import Course, Module, Lesson, Enrollment, Progress, Note, GameScore
from .emails import send_course_renewal_reminder_email

@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('id', 'title', 'price_display', 'is_active_badge', 'sort_order')
    list_display_links = ('id', 'title')
    list_filter = ('is_active',)
    search_fields = ('title', 'slug')

    @display(description="ราคา")
    def price_display(self, obj):
        return f"฿{obj.price:,.2f}"

    @display(description="สถานะ", boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = ('id', 'title', 'course', 'sort_order', 'is_active_badge')
    list_filter = ('course', 'is_active')
    search_fields = ('title',)

    @display(description="สถานะ", boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active


@admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = ('id', 'title', 'course', 'module', 'is_free_badge', 'is_active_badge', 'sort_order')
    list_filter = ('course', 'module', 'is_free', 'is_active')
    search_fields = ('title',)

    @display(description="ทดลองเรียนฟรี", boolean=True)
    def is_free_badge(self, obj):
        return obj.is_free

    @display(description="สถานะ", boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active


@admin.register(Enrollment)
class EnrollmentAdmin(ModelAdmin):
    list_display = ('id', 'user_info', 'course', 'status_badge', 'is_active_badge', 'is_lifetime_badge', 'video_expires_at')
    list_filter = ('course', 'status', 'is_active', 'is_lifetime_video')
    search_fields = ('user__email', 'user__name', 'course__title')
    actions = ['send_renewal_reminder_action']

    @display(description="ผู้เรียน")
    def user_info(self, obj):
        return f"{obj.user.name or obj.user.email} ({obj.user.email})"

    @display(
        description="สถานะสิทธิ์",
        label={
            "ACTIVE": "success",
            "EXPIRED": "danger",
            "SUSPENDED": "warning",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @display(description="เปิดใช้งาน", boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active

    @display(description="ตลอดชีพ", boolean=True)
    def is_lifetime_badge(self, obj):
        return obj.is_lifetime_video

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
class ProgressAdmin(ModelAdmin):
    list_display = ('id', 'user', 'lesson', 'video_time', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'completed_at')
    search_fields = ('user__email', 'lesson__title')


@admin.register(Note)
class NoteAdmin(ModelAdmin):
    list_display = ('id', 'user', 'lesson', 'updated_at')
    search_fields = ('user__email', 'lesson__title', 'content')


@admin.register(GameScore)
class GameScoreAdmin(ModelAdmin):
    list_display = ('id', 'user', 'player_name', 'jlpt_level', 'game_mode', 'score', 'created_at')
    list_filter = ('jlpt_level', 'game_mode', 'created_at')
    search_fields = ('user__email', 'player_name', 'game_mode')
