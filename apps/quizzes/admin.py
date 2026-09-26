from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Quiz, QuizQuestion, QuizAttempt, Vocabulary

@admin.register(Quiz)
class QuizAdmin(ModelAdmin):
    list_display = ('id', 'title', 'lesson', 'created_at')
    search_fields = ('title', 'lesson__title')


@admin.register(QuizQuestion)
class QuizQuestionAdmin(ModelAdmin):
    list_display = ('id', 'quiz', 'question_text', 'correct_option', 'created_at')
    list_filter = ('correct_option', 'created_at')
    search_fields = ('question_text', 'quiz__title')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(ModelAdmin):
    list_display = ('id', 'user', 'quiz', 'score', 'total_questions', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'quiz__title')


@admin.register(Vocabulary)
class VocabularyAdmin(ModelAdmin):
    list_display = ('id', 'kanji', 'reading', 'meaning', 'level_name', 'created_at')
    list_filter = ('level_name', 'created_at')
    search_fields = ('kanji', 'reading', 'meaning')
