from datetime import date
from django.core.management.base import BaseCommand
from courses.models import Enrollment
from courses.emails import send_course_renewal_reminder_email

class Command(BaseCommand):
    help = 'Send course renewal reminder emails to students whose course access is expiring soon or expired.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            nargs='+',
            type=int,
            default=[7, 3, 1],
            help='Days before expiration to send reminder for (default: 7 3 1)'
        )
        parser.add_argument(
            '--include-expired',
            action='store_true',
            help='Also send reminders to enrollments that expired within the last 30 days'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate sending emails without actually delivering them'
        )

    def handle(self, *args, **options):
        days_list = options['days']
        include_expired = options['include_expired']
        dry_run = options['dry_run']

        today = date.today()
        self.stdout.write(self.style.SUCCESS(f"=== Starting Course Renewal Reminder Job (Date: {today}) ==="))

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN MODE ENABLED - No real emails will be sent]"))

        # Base queryset: Active/Expired enrollments with expiration dates, excluding lifetime
        enrollments = Enrollment.objects.filter(
            is_lifetime_video=False,
            video_expires_at__isnull=False
        ).select_related('user', 'course')

        sent_count = 0
        failed_count = 0

        for enrollment in enrollments:
            expires_at = enrollment.video_expires_at
            days_until_exp = (expires_at - today).days

            should_send = False
            reason = ""

            if days_until_exp in days_list:
                should_send = True
                reason = f"Expiring in {days_until_exp} days ({expires_at})"
            elif include_expired and -30 <= days_until_exp < 0:
                should_send = True
                reason = f"Expired {abs(days_until_exp)} days ago ({expires_at})"

            if should_send:
                user_email = enrollment.user.email if enrollment.user else "Unknown"
                course_title = enrollment.course.title if enrollment.course else "Unknown"
                
                self.stdout.write(f"Target: {user_email} | Course: {course_title} | Reason: {reason}")
                
                if not dry_run:
                    ok = send_course_renewal_reminder_email(enrollment, days_remaining=days_until_exp)
                    if ok:
                        sent_count += 1
                    else:
                        failed_count += 1
                else:
                    sent_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"=== Completed Renewal Reminder Job: {sent_count} queued/sent, {failed_count} failed ==="
        ))
