import urllib
import datetime

from django import template
from django.db.models import Sum

from django.core.urlresolvers import reverse

from dateutil.relativedelta import relativedelta

from timepiece.models import PersonRepeatPeriod, AssignmentAllocation


register = template.Library()


@register.filter
def seconds_to_hours(seconds):
    return round(seconds/3600.0, 2)


@register.inclusion_tag('timepiece/time-sheet/bar_graph.html',
                        takes_context=True)
def bar_graph(context, name, worked, total, width=None, suffix=None):
    if not width:
        width = 400
        suffix = 'px'
    left = total - worked
    over = 0
    over_total = 0
    error = ''
    if worked < 0:
        error = 'Somehow you\'ve logged %s negative hours for %s this week.' % (abs(worked), name)
    if left < 0:
        over = abs(left)
        left = 0
        worked = total
        total = over + total
    return { 
        'name': name, 'worked': worked, 
        'total': total, 'left':left,
        'over': over, 'width': width, 
        'suffix': suffix, 'error': error,
        }


@register.inclusion_tag('timepiece/time-sheet/my_ledger.html',
                        takes_context=True)
def my_ledger(context):
    try:
        period = PersonRepeatPeriod.objects.get(user = context['request'].user)
    except PersonRepeatPeriod.DoesNotExist:
        return { 'period': False }
    return { 'period': period }


@register.inclusion_tag('timepiece/time-sheet/_date_filters.html', takes_context=True)
def date_filters(context, options):
    request = context['request']
    from_slug = 'from_date'
    to_slug = 'to_date'
    use_range = True
    if not options:
        options = ('months', 'quaters', 'years')
    
    def construct_url(from_date, to_date):
        url = '%s?%s=%s' % (
            request.path,
            to_slug,
            to_date.strftime('%m/%d/%Y'),
        )
        if use_range:
            url += '&%s=%s' % (
                from_slug,
                from_date.strftime('%m/%d/%Y'),
            )
        return url

    filters = {}
    
    if 'months' in options:
        filters['Past 12 Months'] = []
        single_month = relativedelta(months=1)
        from_date = datetime.date.today().replace(day=1) + relativedelta(months=1)
        for x in range(12):
            to_date = from_date
            from_date = to_date - single_month
            url = construct_url(from_date, to_date - relativedelta(days=1))
            filters['Past 12 Months'].append((from_date.strftime("%b '%y"), url))
        filters['Past 12 Months'].reverse()
    
    if 'years' in options:
        start = datetime.date.today().year - 3
        
        filters['Years'] = []
        for year in range(start, start + 3):
            from_date = datetime.datetime(year, 1, 1)
            to_date = from_date + relativedelta(years=1)
            url = construct_url(from_date, to_date - relativedelta(days=1))
            filters['Years'].append((str(from_date.year), url))

    if 'quaters' in options:
        filters['Quaters (Calendar Year)'] = []
        to_date = datetime.date(datetime.date.today().year - 1, 1, 1)
        for x in range(8):
            from_date = to_date
            to_date = from_date + relativedelta(months=3)
            url = construct_url(from_date, to_date - relativedelta(days=1))
            filters['Quaters (Calendar Year)'].append(
                ('Q%s %s' % ((x % 4) + 1, from_date.year), url)
            )

    return {'filters': filters}


@register.simple_tag
def hours_for_assignment(assignment, date):
    end = date + relativedelta(days=5)
    blocks = assignment.blocks.filter(date__gte=date, date__lte=end).select_related()
    hours = blocks.aggregate(hours=Sum('hours'))['hours']
    if not hours:
        hours = ''
    return hours
    
    
@register.simple_tag
def total_allocated(assignment):
    hours = assignment.blocks.aggregate(hours=Sum('hours'))['hours']
    if not hours:
        hours = ''
    return hours


@register.simple_tag
def hours_for_week(user, date):
    end = date + relativedelta(days=5)
    blocks = AssignmentAllocation.objects.filter(assignment__user=user,
                                                 date__gte=date, date__lte=end)
    hours = blocks.aggregate(hours=Sum('hours'))['hours']
    if not hours:
        hours = ''
    return hours


@register.simple_tag
def weekly_hours_worked(rp, date):
    hours = rp.hours_in_week(date)
    if not hours:
        hours = ''
    return hours


@register.simple_tag
def monthly_overtime(rp, date):
    hours = rp.total_monthly_overtime(date)
    if not hours:
        hours = ''
    return hours


@register.simple_tag
def build_invoice_row(entries, to_date, from_date):
    uninvoiced_hours = invoiced_hours = 0
    for entry in entries:
        activity = entry['activity__pk']
        project = entry['project__pk']
        if entry['status'] == 'invoiced':
            invoiced_hours += entry['s']
        else:
            uninvoiced_hours += entry['s']
    row = '<td>%s</td>' % uninvoiced_hours
    url = reverse('export_project_time_sheet', args=[project,])
    get_str = urllib.urlencode({
        'to_date': to_date.strftime('%m/%d/%Y'), 
        'from_date': from_date.strftime('%m/%d/%Y'),
        'status': 'approved',
        'activity': activity,
    })
    row += '<td><a href="#"><ul class="actions"><li><a href="%s?%s">CSV Timesheet</a></li>' % (url, get_str)
    url = reverse('time_sheet_change_status', args=['invoice',])
    get_str = urllib.urlencode({
        'to_date': to_date.strftime('%m/%d/%Y'), 
        'from_date': from_date.strftime('%m/%d/%Y'),
        'activity': activity,
        'project': project,
    })
    row += '<li><a href="%s?%s">Mark as Invoiced</a></li>' % (url, get_str)
    """
    if invoiced_hours > 0:
        row += '<li><a href="#">(Un)Mark as Invoiced</a></li>'
    Not including invocied hours currently.
    """
    row += '</ul></td>'
    return row
build_invoice_row.is_safe = True
