from django.test import SimpleTestCase

from drl_app.services.transcript_parser import _extract_class_name


class TranscriptClassNameParserTests(SimpleTestCase):
    def test_extracts_class_after_accented_vietnamese_label(self):
        text = "BẢNG ĐIỂM HỌC KỲ\nLớp: CD24CM1\nMSSV Họ tên TBCTK"

        self.assertEqual(_extract_class_name(text), "CD24CM1")

    def test_uses_selected_class_hint_for_spaced_pdf_glyphs(self):
        text = "BẢNG ĐIỂM HỌC KỲ\nLớp: C D 2 4 C M 1\nMSSV Họ tên TBCTK"

        self.assertEqual(
            _extract_class_name(text, expected_class_name="CD24CM1"),
            "CD24CM1",
        )

    def test_does_not_replace_a_different_pdf_class_with_selected_class(self):
        text = "BẢNG ĐIỂM HỌC KỲ\nLớp: CD25CM1\nMSSV Họ tên TBCTK"

        self.assertEqual(
            _extract_class_name(text, expected_class_name="CD24CM1"),
            "CD25CM1",
        )

    def test_does_not_accept_selected_class_as_prefix_of_pdf_class(self):
        text = "BẢNG ĐIỂM HỌC KỲ\nLớp: CD24CM10\nMSSV Họ tên TBCTK"

        self.assertEqual(
            _extract_class_name(text, expected_class_name="CD24CM1"),
            "CD24CM10",
        )
