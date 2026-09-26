from functools import wraps
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.db.models.deletion import Collector, ProtectedError
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .registry import catalogue, LABELS, COLUMNS, allowed, menu
from .forms import form_for


def staff(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('backoffice:login')
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def page(request, template, **context):
    return render(request, 'backoffice/' + template, {'menu': menu(request.user), **context})


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if form.get_user().is_staff:
            login(request, form.get_user())
            return redirect('backoffice:dashboard')
        form.add_error(None, 'บัญชีนี้ไม่มีสิทธิ์เข้าหลังบ้าน')
    return render(request, 'backoffice/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('backoffice:login')


@staff
def password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'เปลี่ยนรหัสผ่านแล้ว')
        return redirect('backoffice:dashboard')
    return page(request, 'form.html', form=form, title='เปลี่ยนรหัสผ่าน')


def resolve(request, app, name, action='view'):
    model = catalogue().get(f'{app}/{name}')
    if not model:
        raise Http404
    if not allowed(request.user, model, action):
        raise PermissionDenied
    return model


def audit(request, obj, action, message):
    # Store action names only, never form values or secrets.
    LogEntry.objects.log_action(user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=str(obj.pk), object_repr=f'{obj._meta.verbose_name} #{obj.pk}'[:200],
        action_flag=action, change_message=message)


@staff
def dashboard(request):
    from courses.models import Course
    from payments.models import Payment
    User = get_user_model()
    cards = []
    for model, label, query in [(User, 'นักเรียน', User.objects.filter(role='student')),
                                (Course, 'คอร์สเรียน', Course.objects.filter(is_active=True)),
                                (Payment, 'สลิปรอตรวจ', Payment.objects.filter(status='pending'))]:
        if allowed(request.user, model):
            cards.append({'label': label, 'value': query.count(),
                          'url': reverse('backoffice:list', args=[model._meta.app_label, model._meta.model_name])})
    recent = []
    revenue = None
    if allowed(request.user, Payment):
        recent = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:8]
        revenue = Payment.objects.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0
    return page(request, 'dashboard.html', title='ภาพรวมระบบ', cards=cards, recent=recent, revenue=revenue)


def visible_fields(model):
    hidden = {'password', 'code_hash', 'video_url', 'key_value', 'user_permissions', 'groups'}
    return [f for f in model._meta.fields if f.name not in hidden]


def display(obj, field):
    value = getattr(obj, field.name)
    if field.choices:
        return getattr(obj, f'get_{field.name}_display')()
    if isinstance(value, bool):
        return 'ใช่' if value else 'ไม่ใช่'
    return str(value) if value is not None else '—'


@staff
def records(request, app, name):
    model = resolve(request, app, name)
    fields = visible_fields(model)
    by_name = {f.name: f for f in fields}
    columns = [by_name[n] for n in COLUMNS.get(name, []) if n in by_name] or fields[:6]
    query = model.objects.all().order_by('-pk')
    relations = [f.name for f in fields if isinstance(f, models.ForeignKey)]
    if relations:
        query = query.select_related(*relations)
    q = request.GET.get('q', '').strip()[:200]
    if q:
        condition = Q()
        for f in fields:
            if isinstance(f, (models.CharField, models.TextField)):
                condition |= Q(**{f'{f.name}__icontains': q})
        if condition:
            query = query.filter(condition)
    filters = []
    for f in fields:
        options = list(f.choices) if f.choices else ( [('1', 'ใช่'), ('0', 'ไม่ใช่')] if isinstance(f, models.BooleanField) else [])
        if isinstance(f, models.ForeignKey) and f.name in {'course', 'module', 'user', 'quiz'} and allowed(request.user, f.related_model):
            options = [(str(item.pk), str(item)[:100]) for item in f.related_model.objects.all().order_by('pk')[:500]]
            selected = request.GET.get(f.name, '')
            if selected and selected not in [key for key, _ in options]:
                try:
                    item = f.related_model.objects.filter(pk=selected).first()
                except (ValueError, TypeError):
                    item = None
                if item:
                    options.append((str(item.pk), str(item)[:100]))
        if options:
            value = request.GET.get(f.name, '')
            if value in [str(k) for k, _ in options]:
                query = query.filter(**{f.name: value == '1' if isinstance(f, models.BooleanField) else value})
            filters.append({'name': f.name, 'label': f.verbose_name, 'options': [(str(k), v) for k, v in options], 'value': value})
    pagination = Paginator(query, 25).get_page(request.GET.get('page'))
    rows = [{'pk': obj.pk, 'values': [display(obj, f)[:180] for f in columns]} for obj in pagination]
    params = request.GET.copy()
    params.pop('page', None)
    return page(request, 'list.html', title=LABELS[name], app=app, name=name,
                headers=[f.verbose_name for f in columns], rows=rows, pagination=pagination,
                query=params.urlencode(), q=q, filters=filters, can_add=allowed(request.user, model, 'add'))


@staff
def detail(request, app, name, pk):
    from .actions import ACTIONS
    model = resolve(request, app, name)
    obj = get_object_or_404(model, pk=pk)
    logs = LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(model), object_id=str(pk)).select_related('user').order_by('-action_time')[:30]
    slip_url = None
    if name == 'payment' and obj.slip_path and '/' not in obj.slip_path and '\\' not in obj.slip_path:
        slip_url = '/storage/slips/' + quote(obj.slip_path)
    related_links = []
    targets = {'course': [('courses', 'module', 'course'), ('courses', 'lesson', 'course'), ('courses', 'enrollment', 'course')],
               'user': [('courses', 'enrollment', 'user'), ('payments', 'payment', 'user')],
               'module': [('courses', 'lesson', 'module')], 'quiz': [('quizzes', 'quizquestion', 'quiz')]}
    for target_app, target_name, field in targets.get(name, []):
        target = catalogue().get(f'{target_app}/{target_name}')
        if target and allowed(request.user, target):
            related_links.append({'label': LABELS[target_name], 'url': reverse('backoffice:list', args=[target_app, target_name]) + '?' + field + '=' + quote(str(pk))})
    return page(request, 'detail.html', title=LABELS[name], app=app, name=name, obj=obj, related_links=related_links,
        actions=[(key, action[0]) for key, action in ACTIONS.get(name, {}).items()],
        fields=[(f.verbose_name, display(obj, f)) for f in visible_fields(model)], logs=logs,
        can_change=allowed(request.user, model, 'change'), can_delete=allowed(request.user, model, 'delete'), slip_url=slip_url)


@staff
def edit(request, app, name, pk=None):
    model = resolve(request, app, name, 'change' if pk is not None else 'add')
    obj = get_object_or_404(model, pk=pk) if pk is not None else None
    if name == 'payment' and obj and obj.status != 'pending':
        messages.error(request, 'รายการตรวจสอบแล้วไม่สามารถแก้ไขได้')
        return redirect('backoffice:detail', app, name, pk)
    form = form_for(model)(request.POST if request.method == 'POST' else None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            audit(request, saved, CHANGE if obj else ADDITION, 'แก้ไขข้อมูล' if obj else 'เพิ่มข้อมูล')
        messages.success(request, 'บันทึกข้อมูลแล้ว')
        return redirect('backoffice:detail', app, name, saved.pk)
    return page(request, 'form.html', title=('แก้ไข ' if obj else 'เพิ่ม ') + LABELS[name], form=form, app=app, name=name)


@staff
def delete(request, app, name, pk):
    model = resolve(request, app, name, 'delete')
    obj = get_object_or_404(model, pk=pk)
    blocked = False
    related = []
    try:
        collector = Collector(using='default')
        collector.collect([obj])
        for related_model, items in collector.data.items():
            if items and (related_model != model or len(items) > 1):
                related.append(f'{related_model._meta.verbose_name}: {len(items)}')
        for query in collector.fast_deletes:
            count = query.count()
            if count:
                related.append(f'{query.model._meta.verbose_name}: {count}')
        blocked = bool(related)
    except ProtectedError:
        blocked = True
        related = ['มีข้อมูลอื่นอ้างอิงรายการนี้']
    if request.method == 'POST' and not blocked:
        with transaction.atomic():
            audit(request, obj, DELETION, 'ลบข้อมูล')
            obj.delete()
        messages.success(request, 'ลบรายการแล้ว')
        return redirect('backoffice:list', app, name)
    return page(request, 'delete.html', title='ยืนยันลบ ' + LABELS[name], obj=obj, blocked=blocked, related=related)


@staff
@require_POST
def review_payment(request, pk):
    from payments.models import Payment
    from courses.models import Enrollment
    from courses.services import AccessService
    if not allowed(request.user, Payment, 'change'):
        raise PermissionDenied
    action = request.POST.get('action')
    if action not in ('approve', 'reject'):
        raise Http404
    with transaction.atomic():
        payment = get_object_or_404(Payment.objects.select_for_update(), pk=pk)
        if payment.status != 'pending':
            messages.warning(request, 'รายการนี้ตรวจสอบแล้ว ไม่มีการบวกยอดซ้ำ')
        elif action == 'reject' and not request.POST.get('reason', '').strip():
            messages.error(request, 'กรุณาระบุเหตุผลที่ปฏิเสธ')
        elif action == 'approve' and (payment.amount <= 0 or payment.duration_days <= 0):
            messages.error(request, 'ยอดชำระและจำนวนวันต้องมากกว่าศูนย์')
        else:
            if action == 'approve':
                user = get_user_model().objects.select_for_update().get(pk=payment.user_id)
                user.total_spent += Decimal(payment.amount)
                user.save(update_fields=['total_spent'])
                AccessService.recalculate_lifetime_unlocks(user.pk)
                enrollment, _ = Enrollment.objects.get_or_create(user=user, course=payment.course)
                enrollment.is_active, enrollment.status = True, 'ACTIVE'
                enrollment.payment_id = payment.pk
                enrollment.activated_at = timezone.now()
                if payment.duration_days == 9999:
                    enrollment.is_lifetime_video = True
                else:
                    base = max(enrollment.video_expires_at or timezone.localdate(), timezone.localdate())
                    enrollment.video_expires_at = base + timedelta(days=payment.duration_days)
                    if payment.is_zoom_included:
                        enrollment.zoom_expires_at = max(enrollment.zoom_expires_at or timezone.localdate(), timezone.localdate()) + timedelta(days=payment.duration_days)
                enrollment.save()
            payment.status = 'approved' if action == 'approve' else 'rejected'
            payment.rejection_reason = request.POST.get('reason', '')[:255] if action == 'reject' else ''
            payment.reviewed_by, payment.reviewed_at = request.user, timezone.now()
            payment.save()
            audit(request, payment, CHANGE, 'อนุมัติการชำระเงิน' if action == 'approve' else 'ปฏิเสธการชำระเงิน')
            messages.success(request, 'บันทึกผลตรวจสลิปแล้ว')
    return redirect('backoffice:detail', 'payments', 'payment', pk)
