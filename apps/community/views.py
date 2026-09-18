import os
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import Post, PostImage, PostLike, Comment
from .services import CommunityModerationService

class PostListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        category = request.query_params.get('category')
        search = request.query_params.get('search')
        
        posts = Post.objects.exclude(moderation_status='REJECTED')
        
        if category and category != 'ALL':
            posts = posts.filter(category=category)
        if search:
            posts = posts.filter(title__icontains=search) | posts.filter(content__icontains=search)

        posts = posts.order_by('-created_at')[:50]

        data = []
        user = request.user if request.user.is_authenticated else None

        for post in posts:
            images = [img.image_url for img in post.images.all()]
            is_liked = False
            if user:
                is_liked = PostLike.objects.filter(user=user, post=post).exists()

            data.append({
                'id': post.id,
                'user': {
                    'id': post.user.id,
                    'name': post.user.name,
                    'email': post.user.email,
                    'role': post.user.role,
                },
                'category': post.category,
                'category_display': post.get_category_display(),
                'title': post.title,
                'content': post.content,
                'images': images,
                'views_count': post.views_count,
                'likes_count': post.likes_count,
                'is_liked': is_liked,
                'comments_count': post.comments.exclude(moderation_status='REJECTED').count(),
                'moderation_status': post.moderation_status,
                'moderation_reason': post.moderation_reason if post.moderation_status == 'REWRITTEN' else '',
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            })

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        category = request.data.get('category', 'GENERAL')
        title = request.data.get('title', '').strip()
        content = request.data.get('content', '').strip()

        if not title or not content:
            return Response({'error': 'กรุณากรอกหัวข้อกระทู้และเนื้อหาให้ครบถ้วน'}, status=status.HTTP_400_BAD_REQUEST)

        # Handle uploaded images validation (Rule: If images provided, must be between 2 and 5)
        uploaded_files = request.FILES.getlist('images')
        if uploaded_files and (len(uploaded_files) < 2 or len(uploaded_files) > 5):
            return Response({'error': 'ระบบกำหนดให้แนบรูปภาพได้ระหว่าง 2 ถึง 5 ภาพเท่านั้นครับ'}, status=status.HTTP_400_BAD_REQUEST)

        # Moderate content using DeepSeek AI
        mod_result = CommunityModerationService.moderate_content(title, content)
        if mod_result['status'] == 'REJECTED':
            return Response({
                'error': mod_result.get('reason', 'เนื้อหามีความรุนแรงหรือคำไม่เหมาะสมอย่างร้ายแรง ระบบปฏิเสธการโพสต์'),
                'moderation_status': 'REJECTED'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create Post object
        post = Post.objects.create(
            user=request.user,
            category=category,
            title=mod_result['clean_title'],
            content=mod_result['clean_content'],
            original_content=content if mod_result['status'] == 'REWRITTEN' else None,
            moderation_status=mod_result['status'],
            moderation_reason=mod_result.get('reason', '')
        )

        # Save uploaded images to disk and DB
        image_urls = []
        if uploaded_files:
            storage_dir = os.path.join(settings.BASE_DIR, 'storage', 'community')
            os.makedirs(storage_dir, exist_ok=True)

            for idx, file_obj in enumerate(uploaded_files):
                ext = file_obj.name.split('.')[-1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(storage_dir, filename)

                with open(filepath, 'wb+') as destination:
                    for chunk in file_obj.chunks():
                        destination.write(chunk)

                img_url = f"/storage/community/{filename}"
                PostImage.objects.create(post=post, image_url=img_url, sort_order=idx)
                image_urls.append(img_url)

        return Response({
            'message': 'โพสต์กระทู้สำเร็จเรียบร้อยแล้ว' if mod_result['status'] == 'APPROVED' else 'โพสต์กระทู้สำเร็จ (ปรับแต่งถ้อยคำโดย AI เพื่อความสุภาพ)',
            'post': {
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'category': post.category,
                'images': image_urls,
                'moderation_status': post.moderation_status,
                'moderation_reason': post.moderation_reason,
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        }, status=status.HTTP_201_CREATED)


class PostDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        
        # Increment view count
        post.views_count += 1
        post.save(update_fields=['views_count'])

        images = [img.image_url for img in post.images.all()]
        user = request.user if request.user.is_authenticated else None
        is_liked = False
        if user:
            is_liked = PostLike.objects.filter(user=user, post=post).exists()

        comments_qs = post.comments.exclude(moderation_status='REJECTED').order_by('created_at')
        comments_data = [{
            'id': c.id,
            'user': {'id': c.user.id, 'name': c.user.name, 'email': c.user.email},
            'content': c.content,
            'moderation_status': c.moderation_status,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for c in comments_qs]

        return Response({
            'id': post.id,
            'user': {'id': post.user.id, 'name': post.user.name, 'email': post.user.email, 'role': post.user.role},
            'category': post.category,
            'category_display': post.get_category_display(),
            'title': post.title,
            'content': post.content,
            'images': images,
            'views_count': post.views_count,
            'likes_count': post.likes_count,
            'is_liked': is_liked,
            'moderation_status': post.moderation_status,
            'moderation_reason': post.moderation_reason if post.moderation_status == 'REWRITTEN' else '',
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'comments': comments_data
        }, status=status.HTTP_200_OK)


class PostLikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        like, created = PostLike.objects.get_or_create(user=request.user, post=post)

        if not created:
            like.delete()
            post.likes_count = max(0, post.likes_count - 1)
            post.save(update_fields=['likes_count'])
            return Response({'liked': False, 'likes_count': post.likes_count}, status=status.HTTP_200_OK)
        else:
            post.likes_count += 1
            post.save(update_fields=['likes_count'])
            return Response({'liked': True, 'likes_count': post.likes_count}, status=status.HTTP_200_OK)


class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        content = request.data.get('content', '').strip()

        if not content:
            return Response({'error': 'กรุณากรอกข้อความแสดงความคิดเห็น'}, status=status.HTTP_400_BAD_REQUEST)

        # AI Moderation for comments
        mod_result = CommunityModerationService.moderate_content("Comment", content)
        if mod_result['status'] == 'REJECTED':
            return Response({
                'error': mod_result.get('reason', 'ความคิดเห็นมีเนื้อหาไม่เหมาะสมอย่างร้ายแรง ระบบปฏิเสธการโพสต์')
            }, status=status.HTTP_400_BAD_REQUEST)

        comment = Comment.objects.create(
            user=request.user,
            post=post,
            content=mod_result['clean_content'],
            original_content=content if mod_result['status'] == 'REWRITTEN' else None,
            moderation_status=mod_result['status'],
            moderation_reason=mod_result.get('reason', '')
        )

        return Response({
            'id': comment.id,
            'user': {'id': request.user.id, 'name': request.user.name, 'email': request.user.email},
            'content': comment.content,
            'moderation_status': comment.moderation_status,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }, status=status.HTTP_201_CREATED)
