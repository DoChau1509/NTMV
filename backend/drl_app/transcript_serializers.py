from rest_framework import serializers

from .models import TranscriptImport, TranscriptImportItem
from .services.transcript_statistics import CLASSIFICATION_ORDER


class TranscriptImportItemSerializer(serializers.ModelSerializer):
    resolved_full_name = serializers.SerializerMethodField()
    student_id = serializers.CharField(source='student.student_id', read_only=True)

    class Meta:
        model = TranscriptImportItem
        fields = (
            'id',
            'student',
            'student_id',
            'student_code',
            'full_name',
            'resolved_full_name',
            'gpa',
            'classification',
            'status',
            'match_status',
            'remark',
            'absent_sessions',
        )

    def get_resolved_full_name(self, obj):
        if obj.student and obj.student.full_name:
            return obj.student.full_name
        return obj.full_name


class TranscriptImportBaseSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    item_count = serializers.IntegerField(source='total_students', read_only=True)
    summary = serializers.SerializerMethodField()
    summary_percent = serializers.SerializerMethodField()
    valid = serializers.SerializerMethodField()
    class_match = serializers.SerializerMethodField()
    class_id = serializers.IntegerField(source='class_info.id', read_only=True)
    selected_class = serializers.CharField(source='class_info.name', read_only=True)
    source_file_name = serializers.CharField(source='original_filename', read_only=True)

    class Meta:
        model = TranscriptImport
        fields = (
            'id',
            'class_id',
            'class_name',
            'selected_class',
            'semester',
            'school_year',
            'source_file_name',
            'original_filename',
            'pdf_class_name',
            'item_count',
            'uploaded_by',
            'uploaded_by_name',
            'uploaded_at',
            'status',
            'valid',
            'class_match',
            'summary',
            'summary_percent',
        )

    def _summary_payload(self, obj):
        summary_data = obj.summary_data or {}
        counts = summary_data.get('counts') or {}
        percentages = summary_data.get('percentages') or {}
        if not counts:
            counts = {name: 0 for name in CLASSIFICATION_ORDER}
        if not percentages:
            total = obj.total_students or 0
            percentages = {
                name: round((counts.get(name, 0) / total) * 100, 2) if total else 0.0
                for name in CLASSIFICATION_ORDER
            }
        return counts, percentages

    def get_summary(self, obj):
        counts, _ = self._summary_payload(obj)
        return counts

    def get_summary_percent(self, obj):
        _, percentages = self._summary_payload(obj)
        return percentages

    def get_valid(self, obj):
        summary_data = obj.summary_data or {}
        value = summary_data.get('valid')
        if value is not None:
            return value
        return obj.status == 'IMPORTED'

    def get_class_match(self, obj):
        summary_data = obj.summary_data or {}
        value = summary_data.get('class_match')
        if value is not None:
            return value
        return None


class TranscriptImportListSerializer(TranscriptImportBaseSerializer):
    class Meta(TranscriptImportBaseSerializer.Meta):
        fields = TranscriptImportBaseSerializer.Meta.fields


class TranscriptImportDetailSerializer(TranscriptImportBaseSerializer):
    items = TranscriptImportItemSerializer(many=True, read_only=True)

    class Meta(TranscriptImportBaseSerializer.Meta):
        fields = TranscriptImportBaseSerializer.Meta.fields + ('items',)
