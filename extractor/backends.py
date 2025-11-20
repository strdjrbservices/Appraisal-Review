from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class ApprovedUserBackend(ModelBackend):
    """
    Custom authentication backend to allow only approved users to log in.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between a user not existing and a user existing but
            # having the wrong password.
            UserModel().set_password(password)
            return None

        if user.check_password(password):
            # Password is correct, now check for approval.
            # Superusers are always allowed to log in, regardless of approval status.
            if user.is_superuser or (hasattr(user, 'profile') and user.profile.is_approved):
                return user

        return None # Return None for incorrect password or lack of approval