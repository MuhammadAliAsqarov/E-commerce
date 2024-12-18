import uuid
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from rest_framework.serializers import Serializer
from .validators import validate_uz_number
from .utils import generate_otp_code
from .models import User, OTP


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        user = User.objects.create(**validated_data)
        return user


class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ['otp_code', 'otp_key']


class ReSetPasswordSerializer(serializers.ModelSerializer):
    token = serializers.UUIDField()
    password = serializers.CharField(max_length=120)


class UserPasswordSerializer(serializers.Serializer):
    class Meta:
        model = User
        fields = [
            'password'
        ]

        extra_kwargs = {
            "password": {"write_only": True},
        }

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class ResetUserPasswordSerializer(Serializer):
    username = serializers.CharField(max_length=13, validators=[validate_uz_number])


class OTPUserPasswordSerializer(Serializer):
    otp_code = serializers.IntegerField(default=generate_otp_code)
    otp_key = serializers.UUIDField(default=uuid.UUID)


class NewPasswordSerializer(Serializer):
    otp_token = serializers.UUIDField(default=uuid.uuid4)
    password = serializers.CharField(required=True)


class OTPResendSerializer(Serializer):
    otp_key = serializers.UUIDField(default=uuid.uuid4)
