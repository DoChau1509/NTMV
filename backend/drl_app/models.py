from django.contrib.auth.models import AbstractUser, UserManager
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db import models

class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_first_login', False)
        return super().create_superuser(username, email, password, **extra_fields)

    def create_user(self, username, email=None, password=None, **extra_fields):
        # Allow default behavior for regular users
        return super().create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('advisor', 'Cố vấn học tập'),
        ('student', 'Sinh viên'),
        ('organizer', 'Ban tổ chức'),
        ('class_monitor', 'Ban cán sự lớp'),
        ('student_affairs', 'Phòng CTSV'),
        ('academic_affairs', 'Phòng Đào tạo'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    full_name = models.CharField(max_length=150, blank=True)
    student_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    is_first_login = models.BooleanField(default=True)
    plain_password = models.CharField(max_length=128, blank=True, null=True)
    # The avatar is the only enrolled face for attendance verification.
    # The descriptor is generated from that avatar and is never used to search
    # across other users.
    avatar = models.TextField(blank=True, default='')
    avatar_embedding = models.JSONField(blank=True, null=True)

    objects = CustomUserManager()

    @property
    def roles(self):
        roles_list = [self.role]
        
        # Check if student_profile is prefetched or exists
        student = None
        if 'student_profile' in self.__dict__:
            student = self.student_profile
        else:
            try:
                student = self.student_profile
            except AttributeError:
                pass
            except User.student_profile.RelatedObjectDoesNotExist:
                pass

        if student:
            # Check if student positions are prefetched
            prefetched_positions = getattr(student, '_prefetched_objects_cache', {}).get('positions')
            if prefetched_positions is not None:
                has_monitor_pos = any(
                    getattr(pos, 'position', None) and getattr(pos.position, 'name', '') in ['Lớp trưởng', 'Lớp phó']
                    for pos in prefetched_positions
                )
            else:
                has_monitor_pos = StudentClassPosition.objects.filter(
                    student=student,
                    position__name__in=['Lớp trưởng', 'Lớp phó']
                ).exists()
            if has_monitor_pos and 'class_monitor' not in roles_list:
                roles_list.append('class_monitor')
                if 'student' not in roles_list:
                    roles_list.append('student')

        # Check if user_organizations is prefetched
        prefetched_orgs = getattr(self, '_prefetched_objects_cache', {}).get('user_organizations')
        if prefetched_orgs is not None:
            has_orgs = len(prefetched_orgs) > 0
        else:
            has_orgs = self.user_organizations.exists()

        if has_orgs and 'organizer' not in roles_list:
            roles_list.append('organizer')

        if self.role == 'class_monitor' and 'student' not in roles_list:
            roles_list.append('student')
        return roles_list

    class Meta:
        db_table = 'user'

    def __str__(self):
        return f"{self.full_name or self.username} ({self.get_role_display()})"

class Organization(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=100) # e.g. CLB, Khoa, CTSV

    class Meta:
        db_table = 'organization'

    def __str__(self):
        return self.name

class UserOrganization(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_organizations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    position = models.CharField(max_length=100) # e.g. Chủ nhiệm, Phó chủ nhiệm, Phụ trách

    class Meta:
        db_table = 'user_organization'
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.full_name or self.user.username} - {self.organization.name} ({self.position})"


class ClassInfo(models.Model):
    name = models.CharField(max_length=100, unique=True)
    faculty = models.CharField(max_length=100)
    cohort = models.CharField(max_length=50)
    advisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_classes', limit_choices_to={'role': 'advisor'})

    class Meta:
        db_table = 'class_info'

    def __str__(self):
        return self.name

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    class_info = models.ForeignKey(ClassInfo, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    faculty = models.CharField(max_length=100)
    cohort = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=(('Nam', 'Nam'), ('Nữ', 'Nữ')), default='Nam')
    phone = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'student'

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"

class ClassPosition(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'class_position'

    def __str__(self):
        return self.name

class StudentClassPosition(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='positions')
    class_info = models.ForeignKey(ClassInfo, on_delete=models.CASCADE, related_name='student_positions')
    position = models.ForeignKey(ClassPosition, on_delete=models.CASCADE, related_name='student_assignments')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_positions')
    assigned_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_class_position'
        unique_together = ('student', 'class_info', 'position')

    def __str__(self):
        return f"{self.student.full_name} - {self.class_info.name}: {self.position.name}"


class CriteriaSet(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    semester = models.CharField(max_length=20, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'criteria_set'
        ordering = ('-is_active', '-created_at')

    def __str__(self):
        return self.name


class Criterion(models.Model):
    criteria_set = models.ForeignKey(CriteriaSet, on_delete=models.CASCADE, related_name='criteria')
    code = models.CharField(max_length=10) # e.g. I, II, III
    name = models.CharField(max_length=255)
    max_score = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    is_manual = models.BooleanField(default=False)

    class Meta:
        db_table = 'criterion'
        ordering = ('code',)
        constraints = [
            models.UniqueConstraint(fields=('criteria_set', 'code'), name='unique_code_per_criteria_set')
        ]

    def __str__(self):
        return f"{self.code}. {self.name}"

class GroupCriterion(models.Model):
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=255)
    is_single_choice = models.BooleanField(default=False)

    class Meta:
        db_table = 'group_criterion'

    def __str__(self):
        return self.name

class SubItem(models.Model):
    group = models.ForeignKey(GroupCriterion, on_delete=models.CASCADE, related_name='sub_items')
    name = models.TextField()
    max_score = models.IntegerField() # can be negative for penalty

    class Meta:
        db_table = 'sub_item'

    def __str__(self):
        return self.name[:50]

class Evaluation(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Nháp'),
        ('published', 'Đã công bố'),
        ('class_pending', 'Chờ cán sự rà soát'),
        ('advisor_pending', 'Chờ cố vấn duyệt'),
        ('pending', 'Chờ duyệt cấp trường'),
        ('approved', 'Đã duyệt hoàn tất'),
        ('rejected', 'Bị từ chối'),
        ('locked', 'Đã khóa'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='evaluations')
    criteria_set = models.ForeignKey(CriteriaSet, on_delete=models.PROTECT, null=True, blank=True, related_name='evaluations')
    semester = models.CharField(max_length=20) # e.g. HK1, HK2
    year = models.CharField(max_length=20) # e.g. 2024-2025
    note = models.TextField(blank=True, null=True)
    self_submitted_at = models.DateTimeField(null=True, blank=True)
    academic_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    academic_classification = models.CharField(max_length=50, blank=True, null=True)
    raw_score = models.IntegerField(default=0)
    base_score = models.IntegerField(default=0)
    carry_in = models.IntegerField(default=0)
    carry_out = models.IntegerField(default=0)
    surplus_balance = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    classification = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_evaluations')
    review_note = models.TextField(blank=True, null=True)
    class_confirmed = models.BooleanField(default=False)
    version = models.IntegerField(default=1)

    class Meta:
        db_table = 'evaluation'
        unique_together = ('student', 'semester', 'year')

    def __str__(self):
        return f"DRL {self.student.student_id} - {self.semester} {self.year}"

class EvaluationSession(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    )

    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluation_sessions',
    )
    semester = models.CharField(max_length=20)
    year = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(default=timezone.now)
    device_info = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluation_session'
        ordering = ('-last_active', '-created_at')

    def __str__(self):
        target = self.student.student_id if self.student_id else f"{self.semester} {self.year or ''}".strip()
        return f"Evaluation session #{self.pk} - {target}"

class EvaluationDetail(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='details')
    sub_item = models.ForeignKey(SubItem, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    is_rejected = models.BooleanField(default=False)
    reject_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'evaluation_detail'
        unique_together = ('evaluation', 'sub_item')

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(default=50)
    location = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'room'

    def __str__(self):
        return f"{self.name} ({self.capacity} chỗ)"

class Activity(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    points = models.IntegerField()
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name='activities')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    date = models.DateField()
    organizer = models.CharField(max_length=255)
    is_external = models.BooleanField(default=False)
    location = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=(('upcoming', 'Upcoming'), ('completed', 'Completed')), default='upcoming')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=10.850100)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=106.771200)
    radius_meters = models.IntegerField(default=100)
    duration_minutes = models.IntegerField(default=180)
    max_participants = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # New scope and registration fields
    scope_type = models.CharField(max_length=20, choices=(('all', 'Toàn trường'), ('class', 'Lớp'), ('club', 'CLB')), default='all')
    allowed_classes = models.ManyToManyField(ClassInfo, blank=True, related_name='activities')
    allowed_clubs = models.ManyToManyField(Organization, blank=True, related_name='activities')
    is_registration_required = models.BooleanField(default=False)
    registration_start = models.DateTimeField(null=True, blank=True)
    registration_end = models.DateTimeField(null=True, blank=True)
    is_soldier_card_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'activity'

    def __str__(self):
        return self.title

class ActivityParticipant(models.Model):
    STATUS_CHOICES = (
        ('registered', 'Đã đăng ký'),
        ('attended', 'Đã tham gia'),
        ('evidence_submitted', 'Đã nộp minh chứng'),
    )
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='participants')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='activity_participations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')
    evidence_url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'activity_participant'
        unique_together = ('activity', 'student')

class ActivityCheckIn(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='checkins')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='checkins')
    check_in_time = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    gps_accuracy = models.FloatField(null=True, blank=True)
    selfie_file_id = models.CharField(max_length=255, blank=True, null=True)
    face_similarity = models.FloatField(null=True, blank=True)
    face_liveness = models.FloatField(null=True, blank=True)
    face_realness = models.FloatField(null=True, blank=True)
    device_id = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()

    class Meta:
        db_table = 'activity_check_in'

class ActivityCheckOut(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='checkouts')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='checkouts')
    check_out_time = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    gps_accuracy = models.FloatField(null=True, blank=True)
    selfie_file_id = models.CharField(max_length=255, blank=True, null=True)
    face_similarity = models.FloatField(null=True, blank=True)
    face_liveness = models.FloatField(null=True, blank=True)
    face_realness = models.FloatField(null=True, blank=True)
    device_id = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()

    class Meta:
        db_table = 'activity_check_out'

class ActivityAttendance(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    duration_minutes = models.IntegerField(default=0)
    completion_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'activity_attendance'
        unique_together = ('activity', 'student')

class FraudDetection(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='frauds', null=True, blank=True)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='frauds', null=True, blank=True)
    rule_code = models.CharField(max_length=50) # e.g. RULE_1, RULE_5
    severity = models.CharField(max_length=20) # High, Medium, Critical
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fraud_detection'

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=255)
    entity_name = models.CharField(max_length=100)
    entity_id = models.IntegerField(null=True, blank=True)
    before_value = models.TextField(blank=True, null=True)
    after_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'

class ChangeRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    )
    request_type = models.CharField(max_length=100)
    reason = models.TextField()
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_changes')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_changes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'change_request'


class ExternalActivity(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('advisor_approved', 'Advisor Approved'),
        ('need_more_info', 'Need More Information'),
        ('rejected_by_advisor', 'Rejected By Advisor'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='external_activities')
    activity_name = models.CharField(max_length=255)
    organizer_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=255, blank=True, null=True)
    activity_type = models.CharField(max_length=100, blank=True, null=True)
    participation_content = models.TextField(blank=True, null=True)
    proposed_score = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'external_activity'

    def __str__(self):
        return f"{self.activity_name} - {self.student.full_name}"


class EvidenceFile(models.Model):
    activity = models.ForeignKey(ExternalActivity, on_delete=models.CASCADE, related_name='evidence_files')
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64) # SHA256
    file_size = models.IntegerField() # bytes
    file_url = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'evidence_file'

    def __str__(self):
        return self.file_name


class EvidenceReview(models.Model):
    activity = models.ForeignKey(ExternalActivity, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    review_level = models.CharField(max_length=50) # 'advisor' or 'ctsv'
    status = models.CharField(max_length=50) # e.g. Approved, Rejected, Need More Information
    comment = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'evidence_review'


class FraudFlag(models.Model):
    activity = models.ForeignKey(ExternalActivity, on_delete=models.CASCADE, related_name='fraud_flags')
    rule_code = models.CharField(max_length=50) # RULE_1 to RULE_7
    severity = models.CharField(max_length=20) # Low, Medium, High, Critical
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fraud_flag'


class TranscriptImport(models.Model):
    STATUS_CHOICES = (
        ('VALIDATED', 'Validated'),
        ('IMPORTED', 'Imported'),
        ('FAILED', 'Failed'),
    )

    class_info = models.ForeignKey(
        ClassInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transcript_imports',
    )
    class_name = models.CharField(max_length=100, blank=True, default="")
    school_year = models.CharField(max_length=50, blank=True, default="")
    semester = models.CharField(max_length=50, blank=True, null=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transcript_imports',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    pdf_class_name = models.CharField(max_length=100, blank=True, default="")
    total_students = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='VALIDATED')
    preview_data = models.JSONField(default=list, blank=True)
    summary_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'transcript_import'
        ordering = ('-uploaded_at', '-id')

    def __str__(self):
        label = self.class_name or (self.class_info.name if self.class_info else "")
        return f"{label} - {self.uploaded_at:%Y-%m-%d %H:%M}"


class TranscriptImportItem(models.Model):
    STATUS_CHOICES = (
        ('MATCHED', 'Matched'),
        ('NOT_FOUND', 'Not Found'),
        ('CLASS_MISMATCH', 'Class Mismatch'),
        ('DUPLICATE', 'Duplicate'),
    )

    transcript_import = models.ForeignKey(
        TranscriptImport,
        on_delete=models.CASCADE,
        related_name='items',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transcript_import_items',
    )
    student_code = models.CharField(max_length=50)
    full_name = models.CharField(max_length=150, blank=True, default="")
    gpa = models.DecimalField(max_digits=4, decimal_places=2)
    classification = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    match_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MATCHED')
    remark = models.CharField(max_length=255, blank=True, default="")
    absent_sessions = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'transcript_import_item'

    def __str__(self):
        return f"{self.student_code} - {self.classification}"


class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'system_config'

    def __str__(self):
        return self.key


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    unread = models.BooleanField(default=True)
    type = models.CharField(max_length=50, default='system')
    level = models.CharField(max_length=50, default='info')
    action_url = models.CharField(max_length=512, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification'
        ordering = ('-created_at',)

    def __str__(self):
        return f"Notification {self.id} for {self.user.username}"


class ReportDefinition(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    module = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    permission_required = models.CharField(max_length=100) # e.g. admin, student_affairs, advisor, etc.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_definition'

    def __str__(self):
        return f"{self.name} ({self.code})"


class ReportJob(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )
    report_definition = models.ForeignKey(ReportDefinition, on_delete=models.PROTECT, related_name='jobs')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    parameters = models.JSONField(default=dict, blank=True)
    result_count = models.IntegerField(default=0)
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_path = models.CharField(max_length=255, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'report_job'
        ordering = ('-created_at',)

    def __str__(self):
        return f"Job #{self.id} - {self.report_definition.name} ({self.status})"


class EvaluationJob(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    progress = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'evaluation_job'
        ordering = ('-created_at',)

    def __str__(self):
        return f"EvaluationJob #{self.id} ({self.status}) - {self.progress}/{self.total}"




