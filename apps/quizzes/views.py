from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Quiz, QuizQuestion, QuizAttempt

class QuizDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        # Find quiz for this lesson
        quiz = Quiz.objects.filter(lesson_id=lesson_id).first()
        if not quiz:
            return Response({'error': 'ไม่พบแบบฝึกหัดสำหรับบทเรียนนี้'}, status=status.HTTP_404_NOT_FOUND)

        # Get questions
        questions = QuizQuestion.objects.filter(quiz=quiz).order_by('id')
        result_questions = []
        for q in questions:
            result_questions.append({
                'id': q.id,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
            })

        return Response({
            'quiz_id': quiz.id,
            'quiz_title': quiz.title,
            'questions': result_questions
        })

class SubmitQuizView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        quiz_id = request.data.get('quiz_id')
        user_answers = request.data.get('answers', {}) # Dict of {question_id: chosen_option}

        try:
            quiz = Quiz.objects.get(id=quiz_id)
        except Quiz.DoesNotExist:
            return Response({'error': 'ไม่พบแบบฝึกหัด'}, status=status.HTTP_404_NOT_FOUND)

        questions = QuizQuestion.objects.filter(quiz=quiz)
        total_questions = questions.count()
        score = 0
        details = []

        for q in questions:
            chosen = user_answers.get(str(q.id)) or user_answers.get(q.id)
            is_correct = (chosen == q.correct_option)
            if is_correct:
                score += 1
            details.append({
                'question_id': q.id,
                'question_text': q.question_text,
                'chosen': chosen,
                'correct_option': q.correct_option,
                'is_correct': is_correct,
                'explanation': q.explanation
            })

        # Calculate next attempt ID (in legacy database it has auto increment but let's check)
        # Actually quiz_attempts table in SQL has AUTO_INCREMENT enabled:
        # CREATE TABLE `quiz_attempts` (`id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, ...)
        # Yes, it has auto increment!
        attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz,
            score=score,
            total_questions=total_questions
        )

        return Response({
            'attempt_id': attempt.id,
            'score': score,
            'total_questions': total_questions,
            'percentage': int((score / total_questions) * 100) if total_questions > 0 else 0,
            'details': details
        }, status=status.HTTP_201_CREATED)
