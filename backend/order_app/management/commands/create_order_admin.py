import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from order_app.models import OrderAccount


class Command(BaseCommand):
    help = 'Tạo tài khoản admin cho Mộc Order (không dùng tài khoản hệ thống cũ).'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--name', default='Quản trị viên')

    def handle(self, *args, **options):
        # Tạo admin đầu tiên qua terminal; getpass không hiển thị mật khẩu nhập.
        username = options['username'].strip().lower()
        if not username or len(username) > 100 or OrderAccount.objects.filter(username=username).exists():
            raise CommandError('Tên đăng nhập trống, quá dài hoặc đã tồn tại.')
        password = getpass.getpass('Mật khẩu admin: ')
        if len(password) > 128:
            raise CommandError('Mật khẩu tối đa 128 ký tự.')
        if password != getpass.getpass('Nhập lại mật khẩu: '):
            raise CommandError('Mật khẩu không khớp.')
        try:
            # Dùng cùng quy tắc độ mạnh mật khẩu của Django như API tạo nhân viên.
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        account = OrderAccount(username=username, full_name=options['name'][:150], role='admin')
        account.set_password(password)
        account.save()
        self.stdout.write(self.style.SUCCESS(f'Đã tạo admin: {username}'))
