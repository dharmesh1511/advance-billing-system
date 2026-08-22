from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import OTPVerification


class Command(BaseCommand):
    help = "Clean up expired or already verified OTP records from the database."

    def handle(self, *args, **options):
        now = timezone.now()
        deleted_count, _ = OTPVerification.objects.filter(
            expires_at__lt=now
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f"Successfully cleaned up {deleted_count} expired OTP record(s).")
        )
