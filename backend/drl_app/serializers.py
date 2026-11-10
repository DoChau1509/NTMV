from rest_framework import serializers
from django.utils import timezone
from .models import User, ClassInfo, Student, CriteriaSet, Criterion, GroupCriterion, SubItem, Evaluation, EvaluationDetail, Activity, ActivityParticipant, Organization, UserOrganization, ClassPosition, StudentClassPosition, ActivityCheckIn, ActivityCheckOut, ActivityAttendance, FraudDetection, AuditLog, ChangeRequest, ExternalActivity, EvidenceFile, EvidenceReview, FraudFlag, SystemConfig, Notification, Room

class ClassPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassPosition
        fields = ('id', 'name')

class StudentClassPositionSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source='position.name', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)

    class Meta:
        model = StudentClassPosition
        fields = ('id', 'class_info', 'position', 'position_name', 'assigned_by', 'assigned_by_name', 'assigned_date')

class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source='members.count', read_only=True)
    activity_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ('id', 'name', 'type', 'member_count', 'activity_count')

    def validate_name(self, value):
        name = value.strip()
        queryset = Organization.objects.all()
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if any(existing.casefold() == name.casefold() for existing in queryset.values_list('name', flat=True)):
            raise serializers.ValidationError('Đơn vị tổ chức này đã tồn tại.')
        if not name:
            raise serializers.ValidationError('Tên đơn vị không được để trống.')
        return name

    def validate_type(self, value):
        organization_type = value.strip()
        if not organization_type:
            raise serializers.ValidationError('Loại đơn vị không được để trống.')
        return organization_type

    def get_activity_count(self, obj):
        return (
            Activity.objects.filter(organizer__iexact=obj.name).count()
            + ExternalActivity.objects.filter(organizer_name__iexact=obj.name).count()
        )

class UserOrganizationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_type = serializers.CharField(source='organization.type', read_only=True)
    
    class Meta:
        model = UserOrganization
        fields = ('id', 'organization', 'organization_name', 'organization_type', 'position')

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.ReadOnlyField()
    organizations = UserOrganizationSerializer(source='user_organizations', many=True, read_only=True)
    avatar_embedding = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'full_name', 'role', 'roles',
            'student_id', 'plain_password', 'organizations', 'avatar',
            'avatar_embedding',
        )

    def validate_avatar_embedding(self, value):
        if value is None:
            return value
        if not isinstance(value, list) or not 64 <= len(value) <= 2048:
            raise serializers.ValidationError('Dữ liệu khuôn mặt không hợp lệ.')
        try:
            embedding = [float(number) for number in value]
        except (TypeError, ValueError, OverflowError):
            raise serializers.ValidationError('Dữ liệu khuôn mặt không hợp lệ.')
        if any(number != number or abs(number) == float('inf') for number in embedding):
            raise serializers.ValidationError('Dữ liệu khuôn mặt không hợp lệ.')
        return embedding

    def validate_avatar(self, value):
        if value and (
            not value.startswith('data:image/')
            or ';base64,' not in value[:100]
            or len(value) > 3 * 1024 * 1024
        ):
            raise serializers.ValidationError('Ảnh đại diện không hợp lệ hoặc vượt quá 2 MB.')
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get('view')
        if view and getattr(view, 'action', None) == 'list':
            data.pop('avatar', None)
        return data


class ClassInfoSerializer(serializers.ModelSerializer):
    advisor_name = serializers.CharField(source='advisor.full_name', read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassInfo
        fields = ('id', 'name', 'faculty', 'cohort', 'advisor', 'advisor_name', 'student_count')

    def get_student_count(self, obj):
        return obj.students.count()

class StudentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_info.name', read_only=True)
    password = serializers.CharField(source='user.plain_password', read_only=True, default='')
    positions = StudentClassPositionSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = ('id', 'student_id', 'full_name', 'email', 'class_info', 'class_name', 'faculty', 'cohort', 'gender', 'phone', 'password', 'positions')

    def create(self, validated_data):
        student_id = validated_data.get('student_id')
        email = validated_data.get('email')
        full_name = validated_data.get('full_name')

        import string
        import random
        
        username = student_id.lower() if student_id else ""
        user_obj = None
        if username:
            user_obj = User.objects.filter(username__iexact=username).first()
            if not user_obj and student_id:
                user_obj = User.objects.filter(student_id=student_id).first()
                
        if not user_obj and username:
            characters = string.ascii_letters + string.digits
            random_password = ''.join(random.choice(characters) for i in range(8))
            
            user_obj = User.objects.create_user(
                username=username,
                email=email,
                password=random_password,
                role='student',
                full_name=full_name,
                student_id=student_id,
                is_first_login=True,
                plain_password=random_password
            )
        
        validated_data['user'] = user_obj
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = instance.user
        if user:
            student_id = validated_data.get('student_id', instance.student_id)
            email = validated_data.get('email', instance.email)
            full_name = validated_data.get('full_name', instance.full_name)
            
            user.username = student_id.lower()
            user.student_id = student_id
            user.email = email
            user.full_name = full_name
            user.save()
            
        return super().update(instance, validated_data)

class SubItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubItem
        fields = ('id', 'name', 'max_score')

class GroupCriterionSerializer(serializers.ModelSerializer):
    subItems = SubItemSerializer(source='sub_items', many=True, read_only=True)

    class Meta:
        model = GroupCriterion
        fields = ('id', 'name', 'is_single_choice', 'subItems')

class CriteriaSetSerializer(serializers.ModelSerializer):
    criteria_count = serializers.IntegerField(source='criteria.count', read_only=True)
    total_max_score = serializers.SerializerMethodField()

    class Meta:
        model = CriteriaSet
        fields = (
            'id', 'name', 'description', 'semester', 'academic_year',
            'effective_from', 'effective_to', 'is_active', 'criteria_count',
            'total_max_score', 'created_at', 'updated_at'
        )

    def get_total_max_score(self, obj):
        return sum(item.max_score for item in obj.criteria.all())

    def validate(self, attrs):
        effective_from = attrs.get('effective_from', getattr(self.instance, 'effective_from', None))
        effective_to = attrs.get('effective_to', getattr(self.instance, 'effective_to', None))
        if effective_from and effective_to and effective_from > effective_to:
            raise serializers.ValidationError({
                'effective_to': 'Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.'
            })
        return attrs

class CriterionSerializer(serializers.ModelSerializer):
    groups = GroupCriterionSerializer(many=True, read_only=True)

    class Meta:
        model = Criterion
        fields = ('id', 'criteria_set', 'code', 'name', 'max_score', 'description', 'is_manual', 'groups')

class EvaluationDetailSerializer(serializers.ModelSerializer):
    sub_item_id = serializers.IntegerField(source='sub_item.id')
    sub_item_name = serializers.CharField(source='sub_item.name', read_only=True)

    class Meta:
        model = EvaluationDetail
        fields = ('id', 'sub_item_id', 'sub_item_name', 'score', 'is_rejected', 'reject_reason')

class EvaluationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    class_name = serializers.CharField(source='student.class_info.name', read_only=True)
    details = EvaluationDetailSerializer(many=True, read_only=True)
    scores = serializers.SerializerMethodField()
    maximum_score = serializers.SerializerMethodField()
    points_missing = serializers.SerializerMethodField()
    points_excess = serializers.SerializerMethodField()
    is_score_complete = serializers.SerializerMethodField()

    class Meta:
        model = Evaluation
        fields = (
            'id', 'student', 'student_name', 'class_name', 'student_id',
            'semester', 'year', 'note', 'academic_gpa', 'academic_classification',
            'raw_score', 'base_score', 'carry_in', 'carry_out', 'surplus_balance',
            'total_score', 'maximum_score', 'points_missing', 'points_excess',
            'is_score_complete', 'classification',
            'status', 'submitted_at', 'self_submitted_at', 'reviewed_by', 'review_note',
            'class_confirmed', 'version', 'criteria_set', 'details', 'scores'
        )

    def get_maximum_score(self, obj):
        if not hasattr(obj, '_maximum_score_cache'):
            obj._maximum_score_cache = (
                sum(item.max_score for item in obj.criteria_set.criteria.all())
                if obj.criteria_set
                else 100
            )
        return obj._maximum_score_cache

    def get_points_missing(self, obj):
        return max(0, self.get_maximum_score(obj) - obj.total_score)

    def get_points_excess(self, obj):
        calculated_balance = max(
            0,
            obj.raw_score - self.get_maximum_score(obj) - obj.carry_out,
        )
        return max(obj.surplus_balance, calculated_balance)

    def get_is_score_complete(self, obj):
        return self.get_points_missing(obj) == 0

    def get_scores(self, obj):
        # Return key-value pairs of criterion_id: score
        # For our frontend, scores is structured as a mapping of criterion_id -> parent score
        scores = {}
        for detail in obj.details.all():
            # Get the top-level parent criterion for the sub_item
            criterion = detail.sub_item.group.criterion
            scores[str(criterion.id)] = scores.get(str(criterion.id), 0) + detail.score
        
        # Clamp scores within max_score for each criterion
        for crit_id, val in scores.items():
            try:
                c = Criterion.objects.get(id=int(crit_id))
                scores[crit_id] = max(0, min(c.max_score, val))
            except Criterion.DoesNotExist:
                pass
        return scores

class ActivityParticipantSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    class_name = serializers.CharField(source='student.class_info.name', read_only=True)
    checked_in_time = serializers.SerializerMethodField()
    checked_out_time = serializers.SerializerMethodField()

    class Meta:
        model = ActivityParticipant
        fields = ('id', 'student', 'student_id', 'student_name', 'class_name', 'status', 'evidence_url', 'checked_in_time', 'checked_out_time')

    def get_checked_in_time(self, obj):
        cache = getattr(obj.activity, '_prefetched_objects_cache', {})
        if 'checkins' in cache:
            matched = [c for c in cache['checkins'] if c.student_id == obj.student_id]
            if matched:
                matched.sort(key=lambda x: x.check_in_time, reverse=True)
                checkin = matched[0]
            else:
                checkin = None
        else:
            checkin = obj.activity.checkins.filter(student=obj.student).order_by('-check_in_time').first()
        return timezone.localtime(checkin.check_in_time).isoformat() if checkin else None

    def get_checked_out_time(self, obj):
        cache = getattr(obj.activity, '_prefetched_objects_cache', {})
        if 'checkouts' in cache:
            matched = [c for c in cache['checkouts'] if c.student_id == obj.student_id]
            if matched:
                matched.sort(key=lambda x: x.check_out_time, reverse=True)
                checkout = matched[0]
            else:
                checkout = None
        else:
            checkout = obj.activity.checkouts.filter(student=obj.student).order_by('-check_out_time').first()
        return timezone.localtime(checkout.check_out_time).isoformat() if checkout else None

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('id', 'name', 'capacity', 'location')

class ActivitySerializer(serializers.ModelSerializer):
    participants = ActivityParticipantSerializer(many=True, read_only=True)
    check_in_time = serializers.SerializerMethodField()
    max_participants = serializers.IntegerField(min_value=1, default=100)
    room_detail = RoomSerializer(source='room', read_only=True)

    class Meta:
        model = Activity
        fields = ('id', 'title', 'description', 'points', 'criterion', 'date', 'organizer', 'status', 'participants', 'latitude', 'longitude', 'radius_meters', 'duration_minutes', 'max_participants', 'check_in_time', 'start_time', 'end_time', 'scope_type', 'allowed_classes', 'allowed_clubs', 'is_registration_required', 'registration_start', 'registration_end', 'room', 'room_detail', 'is_external', 'location', 'is_soldier_card_enabled')

    def validate_organizer(self, value):
        organizer = value.strip()
        if not Organization.objects.filter(name__iexact=organizer).exists():
            raise serializers.ValidationError(
                'Đơn vị tổ chức chưa có trong danh mục. Vui lòng thêm đơn vị trước.'
            )
        return organizer

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance:
            maximum = attrs.get('max_participants', self.instance.max_participants)
            current_count = self.instance.participants.count()
            if maximum < current_count:
                raise serializers.ValidationError({
                    'max_participants': (
                        f'Số người tối đa không thể nhỏ hơn {current_count} '
                        'sinh viên đã đăng ký.'
                    ),
                })
        return attrs

    def get_check_in_time(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            if hasattr(request.user, 'student_profile') and request.user.student_profile:
                checkin = obj.checkins.filter(student=request.user.student_profile).order_by('-check_in_time').first()
                if checkin:
                    return timezone.localtime(checkin.check_in_time).isoformat()
        return None

class ActivityCheckInSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    
    class Meta:
        model = ActivityCheckIn
        fields = '__all__'

class ActivityCheckOutSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = ActivityCheckOut
        fields = '__all__'

class ActivityAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id_str = serializers.CharField(source='student.student_id', read_only=True)
    class_name = serializers.CharField(source='student.class_info.name', read_only=True)

    class Meta:
        model = ActivityAttendance
        fields = '__all__'

class FraudDetectionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id_str = serializers.CharField(source='student.student_id', read_only=True)
    activity_title = serializers.CharField(source='activity.title', read_only=True)

    class Meta:
        model = FraudDetection
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'

class ChangeRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)

    class Meta:
        model = ChangeRequest
        fields = '__all__'


class EvidenceFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceFile
        fields = '__all__'


class EvidenceReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)

    class Meta:
        model = EvidenceReview
        fields = '__all__'


class FraudFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudFlag
        fields = '__all__'


class ExternalActivitySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id_str = serializers.CharField(source='student.student_id', read_only=True)
    evidence_files = EvidenceFileSerializer(many=True, read_only=True)
    fraud_flags = FraudFlagSerializer(many=True, read_only=True)
    reviews = EvidenceReviewSerializer(many=True, read_only=True)

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), required=False)

    class Meta:
        model = ExternalActivity
        fields = '__all__'

    def validate_organizer_name(self, value):
        organizer = value.strip()
        if not Organization.objects.filter(name__iexact=organizer).exists():
            raise serializers.ValidationError(
                'Đơn vị tổ chức chưa có trong danh mục. Vui lòng thêm đơn vị trước.'
            )
        return organizer


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ('id', 'key', 'value', 'description')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'user', 'title', 'message', 'unread', 'type', 'level', 'action_url', 'created_at')



