from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, ExtractedData

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

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(ExtractedData)
class ExtractedDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'filename', 'section_name', 'created_at', 'updated_at')
    list_filter = ('user', 'section_name', 'created_at')
    search_fields = ('filename', 'user__username', 'section_name')
    readonly_fields = ('created_at', 'updated_at')