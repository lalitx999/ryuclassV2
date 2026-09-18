"""Run: backend/venv/bin/python backend/tests/admin_ui_smoke.py

Uses only an in-memory SQLite database. Never connects to the application DB.
Optionally export HTML for visual QA: RYU_ADMIN_REVIEW_DIR=/tmp/ryu-admin-review.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

import django
django.setup()
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import Client
from django.urls import reverse

with connection.schema_editor() as editor:
    for model in apps.get_models():
        editor.create_model(model)

User = get_user_model()
user = User.objects.create_superuser(email='preview@example.test', password='local-test-only', name='ผู้ดูแลตัวอย่าง')
from courses.models import Course
course = Course.objects.create(title='ภาษาญี่ปุ่น N5 สำหรับผู้เริ่มต้น', slug='n5-preview', price=1500)
client = Client()
client.force_login(user)
review_dir = os.getenv('RYU_ADMIN_REVIEW_DIR')

def check_page(url, name=None, required=()):
    response = client.get(url)
    assert response.status_code == 200, (url, response.status_code)
    html = response.content.decode()
    assert '/static/ryu_admin/theme.css' in html, url
    for text in required:
        assert text in html, (url, text)
    if review_dir and name:
        target = Path(review_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / f'{name}.html').write_text(html)
    return html

html = check_page('/admin/', 'dashboard', ['ภาพรวมการจัดการ', 'กิจกรรมล่าสุดของคุณ'])
assert '1-Click' not in html
for model, model_admin in admin.site._registry.items():
    opts = model._meta
    stem = f'admin:{opts.app_label}_{opts.model_name}'
    name = opts.model_name
    check_page(reverse(stem + '_changelist'), name, ['admin/css/changelists.css', 'id="nav-sidebar"'])
    if model_admin.has_add_permission(type('Request', (), {'user': user})()):
        check_page(reverse(stem + '_add'), name + '-add', ['admin/css/forms.css'])
check_page(reverse('admin:courses_course_change', args=[course.pk]), 'course-change', ['admin/css/forms.css'])
check_page(reverse('admin:users_user_change', args=[user.pk]), 'user-change', ['admin/js/SelectFilter2.js', 'admin/js/inlines.js'])
html = check_page(reverse('admin:courses_course_add') + '?_popup=1', 'popup')
assert 'id="header"' not in html and 'id="nav-sidebar"' not in html
check_page(reverse('admin:password_change'), 'password-change')
check_page(reverse('admin:courses_course_history', args=[course.pk]), 'course-history')
check_page(reverse('admin:courses_course_delete', args=[course.pk]), 'course-delete')
assert client.get('/admin/courses/course/?q=N5').context_data['cl'].result_count == 1
assert client.get('/admin/courses/course/?is_active__exact=0').context_data['cl'].result_count == 0
if review_dir:
    catalog = Path(review_dir) / 'admin' / 'jsi18n'
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / 'index.html').write_bytes(client.get('/admin/jsi18n/').content)
# A real form POST verifies the inherited submit controls and admin save flow.
response = client.post(reverse('admin:courses_course_change', args=[course.pk]), {
    'title': 'N5 updated', 'slug': course.slug, 'price': '1500.00',
    'description': '', 'is_active': 'on', 'sort_order': '0', '_save': 'บันทึก',
})
assert response.status_code == 302, response.content.decode()[:500]
course.refresh_from_db()
assert course.title == 'N5 updated'
check_page('/admin/', 'dashboard', ['N5 updated'])
# Restricted staff must not receive privileged shortcuts or sidebar links.
staff = User.objects.create_user(email='staff@example.test', password='local-test-only', is_staff=True)
ct = ContentType.objects.get_for_model(Course)
permission = Permission.objects.create(content_type=ct, codename='view_course', name='Can view course')
staff.user_permissions.add(permission)
client.force_login(staff)
html = check_page('/admin/', 'restricted')
assert '/admin/payments/payment/' not in html and '/admin/users/user/' not in html
assert '/admin/courses/course/' in html
# Logout is a CSRF-protected POST in the native template, not a broken GET link.
assert client.get(reverse('admin:logout')).status_code == 405
assert client.post(reverse('admin:logout')).status_code == 200
html = check_page('/admin/login/?next=/admin/', 'login', ['เข้าสู่ระบบผู้ดูแล'])
assert 'id="nav-sidebar"' not in html
print(f'PASS: {len(admin.site._registry)} model lists and add forms; change forms, widgets, popup, save, permissions, login and logout. SQLite memory only.')
