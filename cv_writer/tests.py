from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import CvWriter, ProfessionalSummary

User = get_user_model()

class ImproveSummaryViewTestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword'
        )
        
        # Create a test CV
        self.cv = CvWriter.objects.create(
            user=self.user,
            first_name='Test',
            last_name='User'
        )
        
        # Create a professional summary for the user
        self.professional_summary = ProfessionalSummary.objects.create(
            user=self.user,
            summary='A seasoned professional with experience in technology.'
        )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # API endpoint
        self.improve_summary_url = '/api/cv_writer/cv/improve_summary/'

    def test_improve_summary_with_cv_id(self):
        """
        Test improving summary by providing CV ID
        """
        response = self.client.post(
            self.improve_summary_url, 
            {'cv_id': self.cv.id}, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('original', response.data)
        self.assertIn('improved', response.data)
        self.assertNotEqual(
            response.data['original'], 
            response.data['improved']
        )

    def test_improve_summary_with_direct_input(self):
        """
        Test improving summary by providing summary directly
        """
        original_summary = 'A dedicated professional seeking growth opportunities.'
        
        response = self.client.post(
            self.improve_summary_url, 
            {'summary': original_summary}, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('original', response.data)
        self.assertIn('improved', response.data)
        self.assertNotEqual(
            response.data['original'], 
            response.data['improved']
        )

    def test_improve_summary_missing_parameters(self):
        """
        Test API behavior when no parameters are provided
        """
        response = self.client.post(
            self.improve_summary_url, 
            {}, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('hint', response.data)

    def test_improve_summary_invalid_cv_id(self):
        """
        Test API behavior with non-existent CV ID
        """
        response = self.client.post(
            self.improve_summary_url, 
            {'cv_id': 9999},  # Non-existent CV ID
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
