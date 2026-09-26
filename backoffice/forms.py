import base64
import os
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class RecordForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance._meta.pk.name in self.fields:
            self.fields[self.instance._meta.pk.name].disabled = True
        for name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 4
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'})
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})
        if 'video_url' in self.fields:
            from courses.views import decrypt_video_url
            self.fields['video_url'].help_text = 'วาง URL วิดีโอ HTTPS ระบบเข้ารหัสให้ก่อนบันทึก'
            if self.instance.pk:
                self.initial['video_url'] = decrypt_video_url(self.instance.video_url)
                if self.instance.video_url and not self.initial['video_url']:
                    self.fields['video_url'].disabled = True
                    self.fields['video_url'].required = False
                    self.fields['video_url'].help_text = 'ถอดรหัสไม่ได้: คงข้อมูลเดิมไว้ กรุณาตรวจสอบ AES_KEY/AES_IV'
        if self.instance._meta.model_name == 'systemsetting' and 'key_value' in self.fields:
            self.fields['key_value'].widget = forms.PasswordInput(attrs={'class': 'form-control'})
            self.fields['key_value'].required = False
            self.fields['key_value'].help_text = 'เว้นว่างเพื่อคงค่าเดิม'

    def clean(self):
        data = super().clean()
        if data.get('module') and data.get('course') and data['module'].course_id != data['course'].pk:
            self.add_error('module', 'หมวดบทเรียนต้องอยู่ในคอร์สที่เลือก')
        if 'video_url' in self.fields and self.fields['video_url'].disabled:
            data['video_url'] = self.instance.video_url
        elif 'video_url' in data and data['video_url']:
            url = forms.URLField().clean(data['video_url'])
            if not url.startswith('https://'):
                self.add_error('video_url', 'กรุณาใช้ URL ที่ขึ้นต้นด้วย https://')
            else:
                key = os.getenv('AES_KEY', '').encode().ljust(32, b'\0')[:32]
                iv = os.getenv('AES_IV', '').encode()[:16]
                if len(iv) != 16 or not os.getenv('AES_KEY'):
                    self.add_error('video_url', 'ยังไม่ได้ตั้งค่า AES สำหรับวิดีโอ')
                else:
                    raw = url.encode()
                    pad = 16 - len(raw) % 16
                    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
                    encrypted = encryptor.update(raw + bytes([pad]) * pad) + encryptor.finalize()
                    data['video_url'] = base64.b64encode(base64.b64encode(encrypted)).decode()
        if self.instance._meta.model_name == 'systemsetting' and not data.get('key_value'):
            data['key_value'] = self.instance.key_value
        return data


class StudentForm(RecordForm):
    new_password = forms.CharField(label='รหัสผ่านใหม่', required=False, widget=forms.PasswordInput,
                                   help_text='เว้นว่างเพื่อใช้รหัสเดิม')
    class Meta:
        model = get_user_model()
        fields = ['email', 'name', 'nickname', 'phone', 'telegram_chat_id', 'total_spent', 'is_affiliate', 'role', 'is_active', 'is_staff',
                  'is_superuser', 'email_verified']

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        if not self.instance.pk and not password:
            raise ValidationError('กรุณาตั้งรหัสผ่านสำหรับสมาชิกใหม่')
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('new_password'):
            user.set_password(self.cleaned_data['new_password'])
        if commit:
            user.save()
            self.save_m2m()
        return user


def form_for(model):
    if model._meta.model_name == 'user':
        return StudentForm
    excluded = ['password', 'code_hash', 'last_login']
    if model._meta.model_name == 'payment':
        excluded += ['status', 'reviewed_at', 'reviewed_by']
    if model._meta.model_name == 'affiliatepayout':
        excluded += ['status', 'paid_at']
    if model._meta.model_name == 'migrationrequest':
        excluded += ['status', 'processed_at', 'processed_by']
    return forms.modelform_factory(model, form=RecordForm, exclude=excluded)
