from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views import generic

from .models import Course, Enrollment, Question, Choice, Submission

import logging

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}

    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        email = request.POST['email']

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email
        )

        login(request, user)
        return HttpResponseRedirect(reverse('onlinecourse:index'))


def login_request(request):
    context = {}

    if request.method == 'GET':
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse('onlinecourse:index'))

        context['message'] = 'Invalid username or password.'
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return HttpResponseRedirect(reverse('onlinecourse:index'))


def check_if_enrolled(user, course):
    is_enrolled = False

    if user.is_authenticated:
        try:
            enrollment = Enrollment.objects.get(
                user=user,
                course=course
            )
            is_enrolled = True
        except Enrollment.DoesNotExist:
            is_enrolled = False

    return is_enrolled


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        return Course.objects.order_by('-pub_date')[:10]


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    if request.user.is_authenticated:
        Enrollment.objects.get_or_create(
            user=request.user,
            course=course
        )

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


def extract_answers(request):
    submitted_answers = []

    for key in request.POST:
        if key.startswith('question_') or key.startswith('choice'):
            for value in request.POST.getlist(key):
                try:
                    choice_id = int(value)
                    submitted_answers.append(choice_id)
                except (ValueError, TypeError):
                    continue

    return submitted_answers


@login_required
def submit(request, course_id):
    if request.method != 'POST':
        return redirect('onlinecourse:course_details', pk=course_id)

    course = get_object_or_404(Course, pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(enrollment=enrollment)

    selected_answers = extract_answers(request)

    for choice_id in selected_answers:
        choice = get_object_or_404(
            Choice,
            pk=choice_id,
            question__course=course
        )
        submission.choices.add(choice)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


@login_required
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    total_score = 0
    question_results = []

    for question in course.question_set.all():

        all_choices = question.choice_set.all()

        correct_choice_ids = set(
            question.choice_set.filter(
                is_correct=True
            ).values_list('id', flat=True)
        )

        selected_choice_ids = set(
            submission.choices.filter(
                question=question
            ).values_list('id', flat=True)
        )

        is_correct = correct_choice_ids == selected_choice_ids

        if is_correct:
            total_score += question.grade

        choice_results = []

        for choice in all_choices:
            choice_results.append({
                'choice': choice,
                'selected': choice.id in selected_choice_ids,
                'is_correct': choice.is_correct
            })

        question_results.append({
            'question': question,
            'choices': choice_results,
            'is_correct': is_correct
        })

    context = {
        'course': course,
        'submission': submission,
        'grade': total_score,
        'question_results': question_results
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )

