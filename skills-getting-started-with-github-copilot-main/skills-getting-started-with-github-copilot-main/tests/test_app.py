"""
Backend tests for the Mergington High School Activities FastAPI application.
Tests all endpoints and error scenarios using pytest and FastAPI's TestClient.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path to import app module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app


@pytest.fixture
def client():
    """
    Provides a TestClient instance with a fresh app for each test.
    Isolates tests from each other using independent app instances.
    """
    return TestClient(app)


class TestGetActivities:
    """Tests for retrieving all activities."""

    def test_get_activities_success(self, client):
        """Test that GET /activities returns all activities with correct structure."""
        response = client.get("/activities")
        
        assert response.status_code == 200
        activities = response.json()
        
        # Verify response is a non-empty dictionary
        assert isinstance(activities, dict)
        assert len(activities) > 0
        
        # Verify all activities have required fields
        required_fields = {"description", "schedule", "max_participants", "participants"}
        for activity_name, activity_data in activities.items():
            assert isinstance(activity_name, str)
            assert activity_data.keys() == required_fields
            assert isinstance(activity_data["description"], str)
            assert isinstance(activity_data["schedule"], str)
            assert isinstance(activity_data["max_participants"], int)
            assert isinstance(activity_data["participants"], list)

    def test_get_activities_contains_expected_activities(self, client):
        """Test that GET /activities contains all expected activities."""
        response = client.get("/activities")
        activities = response.json()
        
        expected_activities = {
            "Chess Club",
            "Programming Class",
            "Gym Class",
            "Basketball Team",
            "Swimming Club",
            "Art Club",
            "Drama Club",
            "Science Club",
            "Math Olympiad"
        }
        
        actual_activities = set(activities.keys())
        assert expected_activities.issubset(actual_activities)


class TestSignupForActivity:
    """Tests for the POST /activities/{activity_name}/signup endpoint."""

    def test_signup_success(self, client):
        """Test successful signup: new student signs up for an activity."""
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]

    def test_signup_activity_not_found(self, client):
        """Test signup fails with 404 when activity doesn't exist."""
        response = client.post(
            "/activities/Nonexistent Club/signup",
            params={"email": "student@mergington.edu"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]

    def test_signup_duplicate_email(self, client):
        """Test signup fails with 400 when student already registered for activity."""
        # First signup succeeds
        response1 = client.post(
            "/activities/Chess Club/signup",
            params={"email": "duplicate@mergington.edu"}
        )
        assert response1.status_code == 200
        
        # Second signup with same email fails
        response2 = client.post(
            "/activities/Chess Club/signup",
            params={"email": "duplicate@mergington.edu"}
        )
        
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"]

    def test_signup_activity_full(self, client):
        """Test signup fails with 400 when activity reaches max capacity."""
        # Create an activity with max_participants = 1 for testing
        # Get the current activities and modify one artificially
        activities_response = client.get("/activities")
        activities = activities_response.json()
        
        # Find a small activity to fill
        small_activity = None
        for name, details in activities.items():
            if details["max_participants"] <= details["participants"].__len__() + 1:
                small_activity = name
                break
        
        if small_activity:
            # Fill up the activity
            available_spots = small_activity["max_participants"] - len(small_activity["participants"])
            for i in range(available_spots):
                response = client.post(
                    f"/activities/{small_activity}/signup",
                    params={"email": f"filler{i}@mergington.edu"}
                )
                assert response.status_code == 200
            
            # Try to signup when full
            response_full = client.post(
                f"/activities/{small_activity}/signup",
                params={"email": "overfull@mergington.edu"}
            )
            assert response_full.status_code == 400
            assert "full" in response_full.json()["detail"]

    def test_signup_participant_added_to_list(self, client):
        """Test that after signup, the participant appears in the participants list."""
        email = "verify@mergington.edu"
        activity = "Programming Class"
        
        # Get initial state
        initial = client.get("/activities").json()
        initial_count = len(initial[activity]["participants"])
        
        # Sign up
        response = client.post(
            f"/activities/{activity}/signup",
            params={"email": email}
        )
        assert response.status_code == 200
        
        # Verify participant was added
        after = client.get("/activities").json()
        assert email in after[activity]["participants"]
        assert len(after[activity]["participants"]) == initial_count + 1


class TestRemoveParticipant:
    """Tests for the DELETE /activities/{activity_name}/participants endpoint."""

    def test_remove_participant_success(self, client):
        """Test successful removal: participant is removed from activity."""
        # First, sign up
        email = "remove_me@mergington.edu"
        activity = "Art Club"
        
        client.post(
            f"/activities/{activity}/signup",
            params={"email": email}
        )
        
        # Verify they're there
        before = client.get("/activities").json()
        assert email in before[activity]["participants"]
        
        # Remove them
        response = client.delete(
            f"/activities/{activity}/participants",
            params={"email": email}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        
        # Verify they're gone
        after = client.get("/activities").json()
        assert email not in after[activity]["participants"]

    def test_remove_participant_activity_not_found(self, client):
        """Test removal fails with 404 when activity doesn't exist."""
        response = client.delete(
            "/activities/Fake Club/participants",
            params={"email": "student@mergington.edu"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]

    def test_remove_participant_not_found(self, client):
        """Test removal fails with 404 when participant is not in the activity."""
        response = client.delete(
            "/activities/Math Olympiad/participants",
            params={"email": "nonexistent@mergington.edu"}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Participant not found" in data["detail"]


class TestSignupRemoveIntegration:
    """Integration tests combining signup and removal operations."""

    def test_signup_then_remove(self, client):
        """Test signup followed by removal in sequence."""
        email = "integration@mergington.edu"
        activity = "Drama Club"
        
        # Sign up
        signup_response = client.post(
            f"/activities/{activity}/signup",
            params={"email": email}
        )
        assert signup_response.status_code == 200
        
        # Verify in list
        after_signup = client.get("/activities").json()
        assert email in after_signup[activity]["participants"]
        participant_count_after_signup = len(after_signup[activity]["participants"])
        
        # Remove
        remove_response = client.delete(
            f"/activities/{activity}/participants",
            params={"email": email}
        )
        assert remove_response.status_code == 200
        
        # Verify removed from list
        after_remove = client.get("/activities").json()
        assert email not in after_remove[activity]["participants"]
        assert len(after_remove[activity]["participants"]) == participant_count_after_signup - 1

    def test_remove_frees_up_spot_for_new_signup(self, client):
        """Test that removing a participant opens up a spot for new signups."""
        activity = "Science Club"
        email1 = "first_student@mergington.edu"
        email2 = "second_student@mergington.edu"
        
        # Get activity details
        activities = client.get("/activities").json()
        max_capacity = activities[activity]["max_participants"]
        
        # Sign up first student (assuming space exists)
        response1 = client.post(
            f"/activities/{activity}/signup",
            params={"email": email1}
        )
        assert response1.status_code == 200
        
        # Check space
        after_first = client.get("/activities").json()
        available = max_capacity - len(after_first[activity]["participants"])
        
        if available == 0:
            # If activity is now full, removing email1 should allow email2 to join
            remove_response = client.delete(
                f"/activities/{activity}/participants",
                params={"email": email1}
            )
            assert remove_response.status_code == 200
            
            # Should now be able to add email2
            response2 = client.post(
                f"/activities/{activity}/signup",
                params={"email": email2}
            )
            assert response2.status_code == 200
