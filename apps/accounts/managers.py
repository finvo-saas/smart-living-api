from django.contrib.auth.models import BaseUserManager

from accounts.phone import normalize_bd_phone


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        phone = normalize_bd_phone(phone)
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_phone_verified', True)
        extra_fields.setdefault('name', 'Admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)

    def get_by_natural_key(self, phone):
        """Allow login with 01… / +880… forms of the same number."""
        try:
            phone = normalize_bd_phone(phone)
        except Exception:
            pass
        return self.get(**{self.model.USERNAME_FIELD: phone})
