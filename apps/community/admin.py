from django.contrib import admin, messages
from .models import Post, PostImage, PostLike, Comment

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 0
    fields = ('image_url', 'sort_order', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'user', 'moderation_status', 'views_count', 'likes_count', 'created_at')
    list_filter = ('category', 'moderation_status', 'created_at')
    search_fields = ('title', 'content', 'user__email', 'user__name')
    inlines = [PostImageInline]
    actions = ['approve_posts', 'reject_posts']

    @admin.action(description="✅ อนุมัติกระทู้ (Approve selected posts)")
    def approve_posts(self, request, queryset):
        updated = queryset.update(moderation_status='APPROVED')
        self.message_user(request, f"อนุมัติกระทู้เรียบร้อยแล้ว {updated} รายการ", messages.SUCCESS)

    @admin.action(description="❌ ปฏิเสธกระทู้ (Reject selected posts)")
    def reject_posts(self, request, queryset):
        updated = queryset.update(moderation_status='REJECTED')
        self.message_user(request, f"ปฏิเสธกระทู้เรียบร้อยแล้ว {updated} รายการ", messages.WARNING)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'moderation_status', 'created_at')
    list_filter = ('moderation_status', 'created_at')
    search_fields = ('content', 'user__email', 'post__title')

@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'created_at')
    search_fields = ('user__email', 'post__title')
