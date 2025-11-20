from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Profile
from .comparison import compare_data_sets
from unittest.mock import patch, MagicMock, AsyncMock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
import os
import json

User = get_user_model()

class UserModelTests(TestCase):
    def test_profile_creation_on_user_signup(self):
        """
        Tests that a Profile object with is_approved=False is automatically
        created when a new User is created.
        """
        user = User.objects.create_user(username='testuser', password='password123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, Profile)
        self.assertFalse(user.profile.is_approved)

class AuthViewsTests(TestCase):
    def setUp(self):
        # Unapproved user
        self.unapproved_user = User.objects.create_user(username='unapproved', password='password123')
        # Approved user
        self.approved_user = User.objects.create_user(username='approved', password='password123')
        self.approved_user.profile.is_approved = True
        self.approved_user.profile.save()

    def test_signup_view(self):
        """Tests user registration view."""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'newpassword123',
            'password2': 'newpassword123',
        })
        self.assertEqual(response.status_code, 302) # Redirects on success
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertFalse(new_user.profile.is_approved)

    def test_login_view_approved_user(self):
        """Tests login for an approved user."""
        response = self.client.post(reverse('login'), {
            'username': 'approved',
            'password': 'password123',
        })
        self.assertRedirects(response, reverse('upload_pdf'))
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_login_view_unapproved_user(self):
        """Tests that an unapproved user cannot log in."""
        response = self.client.post(reverse('login'), {
            'username': 'unapproved',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 200) # Stays on login page
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Your account has not been approved by an administrator yet. Please wait for approval.')

    def test_login_view_invalid_credentials(self):
        """Tests login with incorrect password."""
        response = self.client.post(reverse('login'), {
            'username': 'approved',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'Invalid username or password.')

    def test_logout_view(self):
        """Tests user logout."""
        self.client.login(username='approved', password='password123')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertFalse('_auth_user_id' in self.client.session)

class ProtectedViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.user.profile.is_approved = True
        self.user.profile.save()

    def test_upload_pdf_requires_login(self):
        """Tests that the upload_pdf view is protected by login."""
        response = self.client.get(reverse('upload_pdf'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('upload_pdf')}")

        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('upload_pdf'))
        self.assertEqual(response.status_code, 200)

class ComparisonLogicTests(TestCase):
    def test_compare_data_sets(self):
        """Tests the data comparison logic with various matching rules."""
        html_data = {
            'Client/Lender Name': 'Test Lender, Inc.',
            'Property Address': '123 Main St, Anytown, USA 12345',
            'Transaction Type': 'Purchase',
            'Unit Number': 'N/A',
            'Assigned to Vendor(s)': 'John Smith',
            'FHA Case Number': '123-4567890'
        }
        pdf_data = {
            'Client/Lender Name': 'Test Lender Inc', # Missing comma
            'Property Address': '123 Main St Anytown USA 12345', # Missing commas and spaces
            'Transaction Type': 'Purchase Transaction', # Substring
            'Unit Number': 'N/A',
            'Assigned to Vendor(s)': 'Mr. John David Smith', # Contains name
            'FHA Case Number': '123-4567890'
        }
        results = compare_data_sets(html_data, pdf_data)
        
        # Create a dictionary of results for easy lookup
        results_dict = {item['field']: item for item in results}

        self.assertTrue(results_dict['Client/Lender Name']['match'])
        self.assertTrue(results_dict['Property Address']['match'])
        self.assertTrue(results_dict['Transaction Type']['match'])
        self.assertTrue(results_dict['Unit Number']['match'])
        self.assertTrue(results_dict['Assigned to Vendor(s)']['match'])
        self.assertTrue(results_dict['FHA Case Number']['match'])

class AsyncViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.user.profile.is_approved = True
        self.user.profile.save()
        self.client.login(username='testuser', password='password123')

    @patch('extractor.views.extract_fields_from_pdf', new_callable=AsyncMock)
    @patch('django.core.files.storage.FileSystemStorage.path')
    @patch('django.core.files.storage.FileSystemStorage.exists')
    async def test_extract_section_view(self, mock_exists, mock_path, mock_extract):
        """Tests the extract_section view by mocking the external API call."""
        mock_exists.return_value = True
        mock_path.return_value = '/fake/path/to/file.pdf'
        mock_extract.return_value = {'FHA': '123-4567890', 'Borrower': 'Test Borrower'}

        filename = 'test.pdf'
        section_name = 'subject'
        response = await self.client.get(reverse('extract_section', args=[filename, section_name]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'result.html')
        self.assertIn('data', response.context)
        self.assertEqual(response.context['data']['Borrower'], 'Test Borrower')
        mock_extract.assert_called_once_with('/fake/path/to/file.pdf', section_name, custom_prompt=None)
