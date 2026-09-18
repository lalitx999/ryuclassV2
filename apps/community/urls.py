from django.urls import path
from .views import PostListCreateView, PostDetailView, PostLikeToggleView, CommentCreateView

urlpatterns = [
    path('posts/', PostListCreateView.as_view(), name='community-posts-list-create'),
    path('posts/<int:pk>/', PostDetailView.as_view(), name='community-post-detail'),
    path('posts/<int:pk>/like/', PostLikeToggleView.as_view(), name='community-post-like-toggle'),
    path('posts/<int:pk>/comments/', CommentCreateView.as_view(), name='community-comment-create'),
]
