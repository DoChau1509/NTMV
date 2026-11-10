from types import SimpleNamespace

from django.test import SimpleTestCase

from drl_app.views import _face_similarity, _verify_attendance_location


class FaceSimilarityTests(SimpleTestCase):
    def test_identical_descriptors_are_a_full_match(self):
        descriptor = [0.01] * 128
        self.assertEqual(_face_similarity(descriptor, descriptor), 1.0)

    def test_invalid_or_non_finite_descriptors_never_match(self):
        self.assertEqual(_face_similarity([0.01] * 128, [float('nan')] * 128), 0.0)
        self.assertEqual(_face_similarity([0.01] * 128, [0.01] * 64), 0.0)


class AttendanceLocationTests(SimpleTestCase):
    activity = SimpleNamespace(
        latitude=10.850100,
        longitude=106.771200,
        radius_meters=100,
    )

    def test_valid_position_inside_activity_radius(self):
        request = SimpleNamespace(data={
            'latitude': 10.850100,
            'longitude': 106.771200,
            'accuracy': 12,
        })
        location, error = _verify_attendance_location(request, self.activity, None)
        self.assertIsNone(error)
        self.assertEqual(location['distance'], 0)

    def test_invalid_position_is_rejected(self):
        request = SimpleNamespace(data={
            'latitude': float('nan'),
            'longitude': 106.771200,
            'accuracy': 12,
        })
        location, error = _verify_attendance_location(request, self.activity, None)
        self.assertIsNone(location)
        self.assertEqual(error.status_code, 400)
