import datetime
from django.db import transaction
from users.models import User
from courses.models import Course, Enrollment

class AccessService:
    LIFETIME_THRESHOLDS = {
        10000.00: 'N5',
        20000.00: 'N4',
        30000.00: 'N3',
        40000.00: 'N2',
        50000.00: 'N1',
    }

    @staticmethod
    def get_tier_progress(total_spent: float) -> dict:
        """
        Calculate lifetime tier status, progress percentage, next tier goal and remaining amount.
        """
        total = float(total_spent or 0.0)
        sorted_thresholds = sorted(AccessService.LIFETIME_THRESHOLDS.items(), key=lambda x: x[0])
        
        current_level = None
        for amt, lvl in sorted_thresholds:
            if total >= amt:
                current_level = lvl

        next_threshold = None
        next_level = None
        for amt, lvl in sorted_thresholds:
            if total < amt:
                next_threshold = amt
                next_level = lvl
                break

        if next_threshold is None:
            max_amt = sorted_thresholds[-1][0]
            return {
                'total_spent': total,
                'current_level': 'N1',
                'next_level': None,
                'next_threshold': max_amt,
                'remaining_amount': 0.0,
                'progress_percent': 100.0,
                'overall_progress_percent': 100.0,
                'is_max_tier': True,
                'badge_label': 'N1 Lifetime (สิทธิ์สูงสุด)',
                'summary_text': '🎉 ได้รับสิทธิ์เรียนตลอดชีพครบทุกระดับแล้ว!'
            }

        prev_amt = 0.0
        for amt, _ in sorted_thresholds:
            if amt < next_threshold:
                prev_amt = amt

        range_total = next_threshold - prev_amt
        range_current = total - prev_amt
        progress_pct = max(0.0, min(100.0, (range_current / range_total) * 100.0)) if range_total > 0 else 0.0
        remaining = next_threshold - total

        badge_label = f"{current_level} Lifetime" if current_level else "เริ่มต้นสะสม"
        summary_text = f"ยอดสะสม ฿{total:,.0f} / ฿{next_threshold:,.0f} (ขาดอีก ฿{remaining:,.0f} ปลดล็อก {next_level})"

        return {
            'total_spent': total,
            'current_level': current_level,
            'next_level': next_level,
            'next_threshold': next_threshold,
            'remaining_amount': remaining,
            'progress_percent': round(progress_pct, 1),
            'overall_progress_percent': round(min(100.0, (total / next_threshold) * 100.0), 1),
            'is_max_tier': False,
            'badge_label': badge_label,
            'summary_text': summary_text
        }

    @staticmethod
    def has_video_access(user_id: int, level: str = 'N5') -> bool:
        """
        Check if user has active video access for a course level
        """
        today = datetime.date.today()
        # Find enrollments for the user that match the course level
        enrollments = Enrollment.objects.filter(user_id=user_id, is_active=True)
        
        for e in enrollments:
            if e.status == 'BANNED':
                return False
            if e.is_lifetime_video:
                # If it's a lifetime enrollment, verify it matches or covers the level.
                # In RyuClass, N1 covers all, N2 covers N2-N5, etc.
                # The course mapping: 1=N5, 2=N4, 3=N3, 4=N2, 5=N1.
                # If level is 'N5' (ID 1) and enrollment is for course N3 (ID 3), they have access!
                level_map = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
                requested_id = level_map.get(level, 1)
                if e.course_id >= requested_id:
                    return True
            elif e.status == 'ACTIVE' and e.video_expires_at and e.video_expires_at >= today:
                level_map = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
                requested_id = level_map.get(level, 1)
                if e.course_id >= requested_id:
                    return True
        return False

    @staticmethod
    def has_zoom_access(user_id: int) -> bool:
        """
        Check if user has active Zoom access
        """
        today = datetime.date.today()
        enrollments = Enrollment.objects.filter(
            user_id=user_id, 
            is_active=True, 
            status='ACTIVE',
            zoom_expires_at__gte=today
        )
        return enrollments.exists()

    @staticmethod
    @transaction.atomic
    def recalculate_lifetime_unlocks(user_id: int) -> None:
        """
        Recalculate lifetime unlocks based on current total_spent
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return

        total = float(user.total_spent)
        
        # Determine which levels are unlocked
        unlocked_levels = []
        for threshold, level in AccessService.LIFETIME_THRESHOLDS.items():
            if total >= threshold:
                unlocked_levels.append(level)

        # Map course levels to IDs
        course_map = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
        
        for lvl, course_id in course_map.items():
            should_have_lifetime = lvl in unlocked_levels
            
            # Fetch existing course model to verify it exists
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                continue

            # Check if enrollment exists
            enrollment = Enrollment.objects.filter(user_id=user_id, course_id=course_id).first()

            if should_have_lifetime:
                # Find maximum ID to get next primary key if creating (in legacy tables without AUTO_INCREMENT, but wait:
                # enrollments table in SQL has AUTO_INCREMENT enabled, but let's check).
                # Actually, in the SQL dump: CREATE TABLE `enrollments` (`id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, ...)
                # Yes, it has AUTO_INCREMENT! So we don't need manual ID handling.
                if enrollment:
                    if not enrollment.is_lifetime_video or enrollment.status != 'ACTIVE' or not enrollment.is_active:
                        enrollment.is_lifetime_video = True
                        enrollment.status = 'ACTIVE'
                        enrollment.is_active = True
                        enrollment.activated_at = datetime.datetime.now()
                        enrollment.save()
                else:
                    # Let Django auto-generate the ID
                    Enrollment.objects.create(
                        user=user,
                        course=course,
                        status='ACTIVE',
                        is_active=True,
                        is_lifetime_video=True,
                        activated_at=datetime.datetime.now()
                    )

    @staticmethod
    @transaction.atomic
    def add_payment(user_id: int, amount: float) -> None:
        """
        Add payment to user's total spent and check for Lifetime unlocks
        """
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return
            
        # 1. Update total_spent
        user.total_spent = float(user.total_spent) + float(amount)
        user.save()

        # 2. Recalculate lifetime tiers
        AccessService.recalculate_lifetime_unlocks(user_id)

    @staticmethod
    def calculate_expiry(days: int, include_zoom: bool) -> dict:
        """
        Calculate expiry dates for a specific package
        """
        today = datetime.date.today()
        video_date = today + datetime.timedelta(days=days)
        zoom_date = None

        if include_zoom:
            if days < 999:
                zoom_date = video_date
            else:
                # Month-end for Lifetime (Wait for 99 THB payment)
                # Next.js / python version: end of current month
                next_month = today.replace(day=28) + datetime.timedelta(days=4)
                zoom_date = next_month - datetime.timedelta(days=next_month.day)

        return {
            'video': video_date,
            'zoom': zoom_date
        }
