from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from courses.models import Enrollment
from courses.services import AccessService

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    fields = ('course', 'status', 'is_active', 'is_lifetime_video', 'video_expires_at', 'zoom_expires_at')
    autocomplete_fields = ('course',)

class UserAdmin(BaseUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'name', 'role', 'total_spent', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    inlines = [EnrollmentInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('RyuClass Profile', {'fields': ('total_spent', 'is_affiliate')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password'),
        }),
    )
    search_fields = ('email', 'name')
    filter_horizontal = ('groups', 'user_permissions')

    def save_model(self, request, obj, form, change):
        # Save user object
        super().save_model(request, obj, form, change)
        
        # When user's total_spent or other details are saved/modified, recalculate their lifetime unlocks
        AccessService.recalculate_lifetime_unlocks(obj.id)

admin.site.register(User, UserAdmin)
