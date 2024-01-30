from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum

from meeting_management.models import Meeting, MeetingRecord, Transcription
from organization_management.models import Usage
from user_management.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
            required=False,
            help="Start date",
        )
        parser.add_argument(
            "--until",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
            required=False,
            help="End date",
        )

    def handle(self, *args, **kwargs):
        start_date = kwargs["since"]
        end_date = kwargs["until"]

        self.stdout.write(
            self.style.WARNING(
                f"Showing statistics for interval {start_date} - {end_date}"
            )
        )

        filter_options = dict()
        if start_date:
            filter_options["created_at__gte"] = start_date
        if end_date:
            filter_options["created_at__lte"] = end_date

        try:
            # Number of created meetings
            num_meeting = Meeting.objects.filter(**filter_options).count()
            self.stdout.write(
                self.style.SUCCESS(f"Meetings created: {num_meeting} meetings")
            )

            # Quota usage
            sum_usage = Usage.objects.filter(
                organization__is_monitored__exact=True,
                usage_type=Usage.UsageTypeEnum.ASR,
                **filter_options,
            ).aggregate(Sum("usage"))
            quota_usage = sum_usage["usage__sum"] if sum_usage["usage__sum"] else 0
            hour = quota_usage // 3600
            minute = (quota_usage % 3600) // 60
            self.stdout.write(
                self.style.SUCCESS(
                    f"Quota usage: {quota_usage} seconds ({hour} hours {minute} minutes)"
                )
            )

            # Number of registered users
            num_users = User.objects.filter().count()
            self.stdout.write(
                self.style.SUCCESS(f"Total users registered: {num_users} users")
            )

            # Last transcription activity
            last_transcript = (
                Transcription.objects.filter(**filter_options)
                .order_by("-created_at")
                .first()
            )
            if last_transcript is not None:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Last transcription activity: {last_transcript.created_at}"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No transcription activity"))

            # Number of successful transcription
            num_offline = MeetingRecord.objects.filter(
                transcription_status=2, **filter_options
            ).count()
            num_realtime = MeetingRecord.objects.filter(
                transcription_status=-2, **filter_options
            ).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Total successful transcription: {num_offline} offline meetings, {num_realtime} realtime meetings"
                )
            )

            # Number of biometric usage
            queryset = MeetingRecord.objects.filter(
                (Q(transcription_status=2) | Q(transcription_status=-2))
                & Q(**filter_options)
            )
            num_meeting_with_cluster = queryset.filter(
                meeting__num_cluster__gt=1
            ).count()
            num_meeting_with_participant = (
                queryset.filter(meeting__participants__id__gte=1).distinct().count()
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Total successful transcription with biometric: {num_meeting_with_cluster} meetings with diarization, {num_meeting_with_participant} meetings with identification"
                )
            )
            return
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"{type(exc).__name__}: {exc}"))
