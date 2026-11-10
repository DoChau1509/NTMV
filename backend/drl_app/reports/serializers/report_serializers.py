from rest_framework import serializers
from ...models import ReportDefinition, ReportJob

class ReportDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportDefinition
        fields = ('id', 'code', 'name', 'description', 'module', 'category', 'permission_required', 'is_active', 'created_at', 'updated_at')


class ReportJobSerializer(serializers.ModelSerializer):
    report_name = serializers.CharField(source='report_definition.name', read_only=True)
    report_code = serializers.CharField(source='report_definition.code', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = ReportJob
        fields = (
            'id', 'report_definition', 'report_code', 'report_name', 'created_by', 
            'created_by_name', 'status', 'parameters', 'result_count', 
            'file_name', 'file_path', 'started_at', 'finished_at', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_by', 'status', 'result_count', 'file_name', 'file_path', 'started_at', 'finished_at')
