from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
import json
from .models import Profile, ExtractionResult

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_approved')
    list_select_related = ('profile',)
    actions = ['approve_users']

    def is_approved(self, obj):
        return obj.profile.is_approved
    is_approved.boolean = True

    def approve_users(self, request, queryset):
        queryset.update(profile__is_approved=True)
    approve_users.short_description = "Approve selected users"

class ExtractionResultAdmin(admin.ModelAdmin):
    list_display = ('filename', 'section_name', 'user', 'created_at', 'updated_at')
    list_filter = ('section_name', 'user', 'created_at')
    search_fields = ('filename', 'section_name', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'extracted_data_pretty', 'backend_validation_pretty', 'frontend_validation_pretty')

    fieldsets = (
        (None, {
            'fields': ('user', 'filename', 'section_name')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Data', {
            'fields': ('extracted_data_pretty', 'backend_validation_pretty', 'frontend_validation_pretty')
        }),
    )

    def extracted_data_pretty(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.extracted_data, indent=4, sort_keys=True))
    extracted_data_pretty.short_description = "Extracted Data"

    def backend_validation_pretty(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.backend_validation, indent=4, sort_keys=True))
    backend_validation_pretty.short_description = "Backend Validation"

    def frontend_validation_pretty(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.frontend_validation, indent=4, sort_keys=True))
    frontend_validation_pretty.short_description = "Frontend Validation"

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(ExtractionResult, ExtractionResultAdmin)