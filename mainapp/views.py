from io import TextIOWrapper
import logging
from django.forms.widgets import SelectDateWidget
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from . import tools, models, forms
from .calendar_generator import Calendar
from django.utils.safestring import mark_safe
from django.urls import reverse
import datetime as dt
from datetime import datetime
import django
import csv
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .forms import FileForm
from django.shortcuts import redirect
from .models import File
from .models import FileFilter
from django.core.validators import RegexValidator

logger = logging.getLogger(__name__)

# Create your views here.
# NOTE ALWAYS use initialize_user(request) at the beginning of a view to make sure current user is valid


def index(request):
    """
    Basic home page
    """
    tools.initialize_user(request)
    # this is now needed because calendar is required to view home page
    tools.create_calendar(request)
    if tools.student_exists(request):
        todo = tools.todo_list(request)
        return render(
            request,
            "mainapp/index.html",
            {"todo": mark_safe(todo), "has_todo": len(todo) != 0,},
        )
    else:
        return render(request, "mainapp/index.html")


def calendar_view(request, month_id=None):
    """
    Shows calendar with events, and check marks for what events are to be deleted
    """
    tools.initialize_user(request)
    # make a calendar for this user. If they already have a calendar, this will do nothing.
    # if this is the null user, this will also do nothing. Will redirect home if calendar
    # still failed creation
    tools.create_calendar(request)

    # calendar failed to be created. head to index page
    if not tools.calendar_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # use today's date for the calendar
    d = tools.get_date(request)
    print("------")
    print(month_id)
    if month_id != None and month_id <= 0:
        return calendar_view(request)
    if month_id != None:
        if month_id % 12 == 0:
            d = d.replace(month=12, day=1, year=int(month_id / 12) - 1)
        else:
            d = d.replace(month=int(month_id % 12), day=1, year=int(month_id / 12))
    else:
        month_id = d.month + 12 * d.year
    # Instantiate our calendar class with today's year and date
    cal = Calendar(d.year, d.month)

    # Call the formatmonth method, which returns our calendar as a table
    html_cal = cal.formatmonth(request=request, withyear=True)
    args = {}
    args["calendar"] = mark_safe(html_cal)
    args["next_month"] = month_id

    m = tools.get_date(request)

    return TemplateResponse(request, "mainapp/calendar.html", args)


def prev_month(request, month_id):
    """
    Returns to previous month on calendar
    """
    tools.initialize_user(request)
    return calendar_view(request, month_id=month_id - 1)


def next_month(request, month_id):
    """
    Returns to next month on calendar
    """
    tools.initialize_user(request)
    return calendar_view(request, month_id=month_id + 1)


def classes(request):
    """
    A list of classes associated with the current user
    """
    print(request.user.id)
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    class_list = tools.get_student(request).classes
    return render(
        request,
        "mainapp/classes.html",
        {"class_list": class_list, "professor": tools.is_professor(request),},
    )


def remove_classes(request, className=None):
    """
    Hidden page that handles removing classes from classes view page
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    if className == None:
        return HttpResponseRedirect(reverse("index"))

    tools.remove_class(request, className)

    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    return HttpResponseRedirect(reverse("classes"))


def all_classes(request):
    """
    A list of all registered classes
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    class_list = list(models.Class.objects.all())
    class_list = [
        clazz for clazz in class_list if clazz not in tools.get_student(request).classes
    ]
    return render(
        request,
        "mainapp/all_classes.html",
        {"class_list": class_list, "my_classes": tools.get_student(request).classes},
    )


def add_classes(request, className):
    """
    Hidden page that handles adding classes from all_classes view page
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    if className == None:
        return HttpResponseRedirect(reverse("index"))

    tools.add_class(request, className)

    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    return HttpResponseRedirect(reverse("classes"))


def delete_assignment(request, className, event_id):
    """
    Hidden page that handles deleting (or checking off) assignments
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    if tools.is_professor_for_class(request, className):
        tools.delete_event(request, event_id, className)
    else:
        tools.check_off(request, event_id, className)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def add_assignment(request, className=None):
    """
    Form page to add assignments to calendar
    """
    tools.initialize_user(request)
    # if this is a post, then add assignment
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # ---------class definition for AddAssignment form---------- #
    # FIXME I hate this, but it is the only way I can think to provide request arguments
    # for the structure of this class. Anyone have any idea to not put this here?
    class AddAssignment(django.forms.Form):
        summary = django.forms.CharField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 30,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;",
                }
            ),
            label="Assignment name:",
            max_length=30,
            required=True,
            # https://stackoverflow.com/questions/17165147/how-can-i-make-a-django-form-field-contain-only-alphanumeric-characters
            validators=[
                RegexValidator(
                    r"^[0-9a-zA-Z ]*$", "Only alphanumeric characters are allowed."
                )
            ],
        )
        est_time = django.forms.IntegerField(
            widget=django.forms.Textarea(
                attrs={
                    "cols": 10,
                    "rows": 1,
                    "style": "border-radius: 7px; border-color: black;",
                }
            ),
            label="Estimated number of hours:",
            max_value=100,
            required=False,
        )
        time = django.forms.DateField(
            input_formats=("%Y-%m-%d",),
            widget=SelectDateWidget(
                empty_label=("Choose Year", "Choose Month", "Choose Day"),
            ),
            # widget=django.forms.Textarea(
            #     attrs={
            #         "cols": 50,
            #         "rows": 1,
            #         "style": "border-radius: 7px; border-color: black;",
            #     }
            # ),
            label="Date of assignment (YYYY-MM-DD)",
            required=True,
        )

    # ------------ end class definition ------------- #

    if request.method == "POST":
        # gather the form
        form = AddAssignment(request.POST)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the assignment

            # get the class. If calendar was not on the form (not a professor) or
            # the professor chose personal, then no class
            # otherwise, it is a professor and they specified a class, pass it on
            if className == "None":
                className = None
            print(form.data, "lookkie here <----------------")
            tools.create_event(
                request,
                form.data["summary"],
                form.data["est_time"],
                datetime(
                    year=int(form.data["time_year"]),
                    month=int(form.data["time_month"]),
                    day=int(form.data["time_day"]),
                ),
                className=className,
            )

            # notify students of event creation, if class is not personal
            if className != None:
                tools.notify_students_of_change(
                    className, form.data["summary"], "create"
                )
            # redirect to the calendar
            if className == None:
                return HttpResponseRedirect(reverse("calendar"))
            return HttpResponseRedirect(
                reverse("view_class", kwargs={"className": className})
            )

    # create a blank form
    else:
        form = AddAssignment()
    # display the webpage (if it was not a post)
    return render(
        request, "mainapp/addassignment.html", {"form": form, "className": className}
    )


def create_class(request):
    """
    View for creating a class. This view is **only** usable by a professor.
    """
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # student is trying to create a class... dont let them! Bring them back home
    if not tools.is_professor(request):
        return HttpResponseRedirect(reverse("index"))

    # if this is a post, then add assignment
    if request.method == "POST":
        # gather the form
        form = forms.CreateClass(request.POST)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the class
            tools.create_class(request, form.data["name"], form.data["description"])

            # add the class for this professor
            tools.add_class(request, form.data["name"])
            # redirect to all class list
            return HttpResponseRedirect(reverse("classes"))

    # create a blank form
    else:
        form = forms.CreateClass()
    # display the webpage (if it was not a post)
    return render(request, "mainapp/create_class.html", {"form": form})


def upload_schedule(request, className):
    """
    View for creating a class. This view is **only** usable by a professor.
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))
    # if this is a post, then upload a schedule
    class UploadSyllabus(django.forms.Form):
        file = django.forms.FileField()

    if request.method == "POST" and request.FILES:
        print(request)
        # gather the form
        form = UploadSyllabus(request.POST, request.FILES)
        # check whether the form fits the constraints:
        if form.is_valid():
            # save the class
            tools.upload_syllabus(request, form, className)
            return HttpResponseRedirect(
                reverse("view_class", kwargs={"className": className})
            )

    # create a blank form
    else:
        form = UploadSyllabus()
    # display the webpage (if it was not a post)
    return render(
        request, "mainapp/upload_schedule.html", {"form": form, "className": className}
    )


def upload_file(request, className=None):
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    if request.method == "POST":
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            print(request.POST["title"])
            models.File.objects.create(
                title=request.POST["title"],
                author=request.user.username,
                className=className,
                pdf=request.FILES["pdf"],
            )
            return redirect("file_list", className=className)
    else:
        form = FileForm()

    return render(
        request, "mainapp/upload_file.html", {"form": form, "className": className}
    )


def delete_file(request, pk, className=None):
    tools.initialize_user(request)

    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    if request.method == "POST":
        file = File.objects.get(pk=pk)
        file.delete()
    return redirect("file_list", className=className)


def file_list(request, className=None):
    """
    Displays a list of files for a certain class with name className
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    f = FileFilter(request.GET, queryset=File.objects.filter(className=className))
    return render(
        request, "mainapp/file_list.html", {"filter": f, "className": className}
    )


def view_class(request, className=None):
    """
    Shows the home page for a class
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # cannot show a class that doesnt exist
    if className == None:
        return HttpResponseRedirect(reverse("index"))

    # cannot show a non-registered class
    if not tools.class_exists(className):
        return HttpResponseRedirect(reverse("index"))

    # render the class page
    todo = tools.todo_list(request, className, editable=True,)
    return render(
        request,
        "mainapp/view_class.html",
        {
            "class": tools.get_class(className),
            "todo": mark_safe(todo),
            "has_todo": len(todo) != 0,
        },
    )


def change_color(request, className=None):
    """
    Change the color for a class given the className
    The given request should have the color id
    """

    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    # change default non-class color
    if className == None:
        tools.set_class_color(request, className, request.POST["colorpicker"])
    elif tools.class_exists(className):
        tools.set_class_color(request, className, request.POST["colorpicker"])
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def todo_list(request):
    """
    The view for the todo list
    """
    tools.initialize_user(request)
    if not tools.student_exists(request):
        return HttpResponseRedirect(reverse("index"))

    todo = tools.todo_list(request, editable=True, todo_loc=True)
    return render(
        request,
        "mainapp/todo_list.html",
        {"todo": mark_safe(todo), "has_todo": len(todo) != 0,},
    )

