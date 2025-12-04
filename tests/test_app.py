"""
Tests for the Mergington High School API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    activities.clear()
    activities.update(original_activities)


class TestGetActivities:
    """Test the GET /activities endpoint"""
    
    def test_get_activities(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert data["Chess Club"]["description"] == "Learn strategies and compete in chess tournaments"
    
    def test_activities_have_required_fields(self, client):
        """Test that activities have all required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_data in data.items():
            assert "description" in activity_data
            assert "schedule" in activity_data
            assert "max_participants" in activity_data
            assert "participants" in activity_data
            assert isinstance(activity_data["participants"], list)


class TestSignup:
    """Test the POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Signed up" in data["message"]
        assert "newstudent@mergington.edu" in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_nonexistent_activity(self, client):
        """Test signup for a non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_signup_duplicate(self, client, reset_activities):
        """Test that a student cannot sign up twice for the same activity"""
        # First signup
        response1 = client.post(
            "/activities/Chess Club/signup?email=duplicate@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Second signup (should fail)
        response2 = client.post(
            "/activities/Chess Club/signup?email=duplicate@mergington.edu"
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_already_registered(self, client):
        """Test signup for someone already registered in an activity"""
        # michael@mergington.edu is already in Chess Club
        response = client.post(
            "/activities/Chess Club/signup?email=michael@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]


class TestUnregister:
    """Test the DELETE /activities/{activity_name}/participants/{email} endpoint"""
    
    def test_unregister_success(self, client, reset_activities):
        """Test successful unregistration of a participant"""
        # michael@mergington.edu is in Chess Club initially
        initial_response = client.get("/activities")
        initial_data = initial_response.json()
        initial_count = len(initial_data["Chess Club"]["participants"])
        
        # Unregister
        response = client.delete(
            "/activities/Chess Club/participants/michael@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Unregistered" in data["message"]
        
        # Verify participant was removed
        final_response = client.get("/activities")
        final_data = final_response.json()
        assert len(final_data["Chess Club"]["participants"]) == initial_count - 1
        assert "michael@mergington.edu" not in final_data["Chess Club"]["participants"]
    
    def test_unregister_nonexistent_activity(self, client):
        """Test unregistration from a non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Club/participants/student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_unregister_nonexistent_participant(self, client, reset_activities):
        """Test unregistration of a participant not in the activity"""
        response = client.delete(
            "/activities/Chess Club/participants/notregistered@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "Participant not found" in data["detail"]
    
    def test_unregister_twice(self, client, reset_activities):
        """Test that you cannot unregister someone twice"""
        # First unregister (should succeed)
        response1 = client.delete(
            "/activities/Chess Club/participants/michael@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Second unregister (should fail)
        response2 = client.delete(
            "/activities/Chess Club/participants/michael@mergington.edu"
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "Participant not found" in data["detail"]


class TestIntegration:
    """Integration tests combining multiple operations"""
    
    def test_signup_unregister_signup_flow(self, client, reset_activities):
        """Test the flow of signup -> unregister -> signup again"""
        email = "integration@mergington.edu"
        activity = "Programming Class"
        
        # Sign up
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        activities_response = client.get("/activities")
        assert email in activities_response.json()[activity]["participants"]
        
        # Unregister
        response2 = client.delete(f"/activities/{activity}/participants/{email}")
        assert response2.status_code == 200
        
        activities_response = client.get("/activities")
        assert email not in activities_response.json()[activity]["participants"]
        
        # Sign up again
        response3 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response3.status_code == 200
        
        activities_response = client.get("/activities")
        assert email in activities_response.json()[activity]["participants"]
    
    def test_multiple_signups(self, client, reset_activities):
        """Test signing up multiple students for the same activity"""
        activity = "Art Studio"
        students = [
            "student1@mergington.edu",
            "student2@mergington.edu",
            "student3@mergington.edu"
        ]
        
        for student in students:
            response = client.post(f"/activities/{activity}/signup?email={student}")
            assert response.status_code == 200
        
        # Verify all are registered
        activities_response = client.get("/activities")
        participants = activities_response.json()[activity]["participants"]
        for student in students:
            assert student in participants
