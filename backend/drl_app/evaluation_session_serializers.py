from rest_framework import serializers
from .models import EvaluationSession

class EvaluationSessionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    evaluation_status = serializers.SerializerMethodField()
    evaluation_total_score = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationSession
        fields = (
            'id',
            'evaluation',
            'student',
            'student_name',
            'student_id',
            'semester',
            'year',
            'status',
            'started_at',
            'last_active',
            'device_info',
            'ip_address',
            'created_at',
            'updated_at',
            'evaluation_status',
            'evaluation_total_score',
        )
        read_only_fields = (
            'started_at',
            'last_active',
            'created_at',
            'updated_at',
            'evaluation_status',
            'evaluation_total_score',
        )

    def get_student_name(self, obj):
        return obj.student.full_name if obj.student else None

    def get_student_id(self, obj):
        return obj.student.student_id if obj.student else None

    def get_evaluation_status(self, obj):
        return obj.evaluation.status if obj.evaluation else None

    def get_evaluation_total_score(self, obj):
        return obj.evaluation.total_score if obj.evaluation else None
