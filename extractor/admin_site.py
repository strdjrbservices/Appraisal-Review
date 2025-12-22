from django.contrib.admin import AdminSite
from django.shortcuts import render
from django.urls import path
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry

UserModel = get_user_model()

class CustomAdminSite(AdminSite):
    # ... (site metadata and user_report_view logic for stats) ...

    def user_report_view(self, request):
        # Calculate user stats
        pending_users = UserModel.objects.filter(profile__is_approved=False).count()
        total_users = UserModel.objects.count()

        # Get recent log entries for the "Recent Actions" module
        # Pass the unsliced queryset to the template. The template tag will handle slicing.
        log_entries = LogEntry.objects.select_related("content_type", "user").order_by("-action_time")

        context = {
            **self.each_context(request),
            'total_users': total_users,
            'pending_users': pending_users,
            'log_entries': log_entries,
        }
        return render(request, 'admin/index.html', context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.user_report_view), name='index'),
            # ... (omitted) ...
        ]
        return custom_urls + urls

custom_admin = CustomAdminSite(name='custom_admin')