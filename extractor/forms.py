from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

class UpdateFileReviewForm(forms.Form):
    revised_report = forms.FileField(label='Revised Report (Required)', required=True, widget=forms.FileInput(attrs={'accept': '.pdf'}))
    old_report = forms.FileField(label='Old Report (Required)', required=True, widget=forms.FileInput(attrs={'accept': '.pdf'}))
    order_form = forms.FileField(label='Order Form HTML (Optional)', required=False, widget=forms.FileInput(attrs={'accept': '.html,.htm'}))
    purchase_copy = forms.FileField(label='Purchase Copy (Optional)', required=False, widget=forms.FileInput(attrs={'accept': '.pdf'}))
    engagement_letter = forms.FileField(label='Engagement Letter (Optional)', required=False, widget=forms.FileInput(attrs={'accept': '.pdf'}))
    custom_prompt = forms.CharField(label='Custom Analysis Prompt', required=False, widget=forms.Textarea(attrs={'rows': 4}))