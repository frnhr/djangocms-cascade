# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import itertools
from django.forms import widgets
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join
from django.utils.encoding import force_text
from django.utils.translation import ungettext_lazy, ugettext_lazy as _
from django.forms.models import ModelForm
from django.forms.fields import ChoiceField
from cms.plugin_pool import plugin_pool
from cmsplugin_cascade.forms import ManageChildrenFormMixin
from cmsplugin_cascade.fields import PartialFormField
from . import settings
from .plugin_base import BootstrapPluginBase
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

BS3_BREAKPOINTS = OrderedDict(settings.CMSPLUGIN_CASCADE['bootstrap3']['breakpoints'])
BS3_BREAKPOINT_KEYS = list(tp[0] for tp in settings.CMSPLUGIN_CASCADE['bootstrap3']['breakpoints'])


class ContainerBreakpointsRenderer(widgets.CheckboxFieldRenderer):
    def render(self):
        return format_html('<div class="form-row">{0}</div>',
            format_html_join('', '<div class="field-box">'
                '<div class="container-thumbnail"><i class="icon-{1}"></i><div class="label">{0}</div></div>'
                '</div>', ((force_text(w), BS3_BREAKPOINTS[w.choice_value][1]) for w in self)
            ))


class BootstrapContainerForm(ModelForm):
    """
    Form class to validate the container.
    """
    def clean_glossary(self):
        if len(self.cleaned_data['glossary']['breakpoints']) == 0:
            raise ValidationError(_("At least one breakpoint must be selected."))
        return self.cleaned_data['glossary']


class BootstrapContainerPlugin(BootstrapPluginBase):
    name = _("Container")
    require_parent = False
    parent_classes = []
    form = BootstrapContainerForm
    breakpoints = list(BS3_BREAKPOINTS)
    i = 0
    widget_choices = []
    for br, br_options in BS3_BREAKPOINTS.items():
        if i == 0:
            widget_choices.append((br, '{} (<{}px)'.format(br_options[2], br_options[0])))
        elif i == len(breakpoints[:-1]):
            widget_choices.append((br, '{} (≥{}px)'.format(br_options[2], br_options[0])))
        else:
            widget_choices.append((br, '{} (≥{}px and <{}px)'.format(br_options[2], br_options[0], BS3_BREAKPOINTS[breakpoints[(i + 1)]][0])))
        i += 1

    WIDGET_CHOICES = tuple(widget_choices)

    glossary_fields = (
        PartialFormField('breakpoints',
            widgets.CheckboxSelectMultiple(choices=WIDGET_CHOICES, renderer=ContainerBreakpointsRenderer),
            label=_('Available Breakpoints'),
            initial=breakpoints[::-1],
            help_text=_("Supported display widths for Bootstrap's grid system.")
        ),
        PartialFormField('fluid',
            widgets.CheckboxInput(),
            label=_('Fluid Container'), initial=False,
            help_text=_("Changing your outermost '.container' to '.container-fluid'.")
        ),
    )
    glossary_variables = ['container_max_widths', 'media_queries']

    class Media:
        css = {'all': ('//netdna.bootstrapcdn.com/font-awesome/3.2.1/css/font-awesome.min.css',)}
        js = ['cascade/js/admin/containerplugin.js']

    @classmethod
    def get_identifier(cls, obj):
        identifier = super(BootstrapContainerPlugin, cls).get_identifier(obj)
        breakpoints = obj.glossary.get('breakpoints')
        content = obj.glossary.get('fluid') and '(fluid) ' or ''
        if breakpoints:
            devices = ', '.join([force_text(BS3_BREAKPOINTS[bp][2]) for bp in breakpoints])
            content = _("{0}for {1}").format(content, devices)
        return format_html('{0}{1}', identifier, content)

    @classmethod
    def get_css_classes(cls, obj):
        css_classes = super(BootstrapContainerPlugin, cls).get_css_classes(obj)
        if obj.glossary.get('fluid'):
            css_classes.append('container-fluid')
        else:
            css_classes.append('container')
        return css_classes

    def save_model(self, request, obj, form, change):
        super(BootstrapContainerPlugin, self).save_model(request, obj, form, change)
        obj.sanitize_children()

    @classmethod
    def sanitize_model(cls, obj):
        sanitized = super(BootstrapContainerPlugin, cls).sanitize_model(obj)
        parent_glossary = obj.get_parent_glossary()
        # compute the max width and the required media queries for each chosen breakpoint
        obj.glossary['container_max_widths'] = max_widths = {}
        obj.glossary['media_queries'] = media_queries = {}
        breakpoints = obj.glossary.get('breakpoints', [])
        last_index = len(breakpoints) - 1
        for index, bp in enumerate(breakpoints):
            try:
                max_widths[bp] = parent_glossary['container_max_widths'][bp]
            except KeyError:
                if obj.glossary.get('fluid'):
                    if bp == 'lg':
                        max_widths[bp] = settings.CMSPLUGIN_CASCADE['bootstrap3']['fluid-lg-width']
                    else:
                        max_widths[bp] = BS3_BREAKPOINTS[bp][0]
                else:
                    max_widths[bp] = BS3_BREAKPOINTS[bp][3]
            if last_index > 0:
                if index == 0:
                    next_bp = breakpoints[1]
                    media_queries[bp] = ['(max-width: {0}px)'.format(BS3_BREAKPOINTS[next_bp][0])]
                elif index == last_index:
                    media_queries[bp] = ['(min-width: {0}px)'.format(BS3_BREAKPOINTS[bp][0])]
                else:
                    next_bp = breakpoints[index + 1]
                    media_queries[bp] = ['(min-width: {0}px)'.format(BS3_BREAKPOINTS[bp][0]),
                                         '(max-width: {0}px)'.format(BS3_BREAKPOINTS[next_bp][0])]
        return sanitized

    def get_parent_classes(self, slot, page):
        if self.cms_plugin_instance and self.cms_plugin_instance.parent:
            # enforce that a ContainerPlugin can't have a parent
            return []
        return super(BootstrapContainerPlugin, self).get_parent_classes(slot, page)

plugin_pool.register_plugin(BootstrapContainerPlugin)


class BootstrapRowForm(ManageChildrenFormMixin, ModelForm):
    """
    Form class to add non-materialized field to count the number of children.
    """
    ROW_NUM_COLUMNS = (1, 2, 3, 4, 6, 12,)
    num_children = ChoiceField(choices=tuple((i, ungettext_lazy('{0} column', '{0} columns', i).format(i)) for i in ROW_NUM_COLUMNS),
        initial=3, label=_('Columns'),
        help_text=_('Number of columns to be created with this row.'))


class BootstrapRowPlugin(BootstrapPluginBase):
    name = _("Row")
    default_css_class = 'row'
    parent_classes = ('BootstrapContainerPlugin', 'BootstrapColumnPlugin',)
    form = BootstrapRowForm
    fields = ('num_children', 'glossary',)

    @classmethod
    def get_identifier(cls, obj):
        identifier = super(BootstrapRowPlugin, cls).get_identifier(obj)
        num_cols = obj.get_children_count()
        content = ungettext_lazy("with {0} column", "with {0} columns", num_cols).format(num_cols)
        return format_html('{0}{1}', identifier, content)

    def save_model(self, request, obj, form, change):
        wanted_children = int(form.cleaned_data.get('num_children'))
        super(BootstrapRowPlugin, self).save_model(request, obj, form, change)
        parent_glossary = obj.get_complete_glossary()
        narrowest = parent_glossary['breakpoints'][0]
        column_width = 12 // wanted_children
        child_glossary = {
            '{0}-column-width'.format(narrowest): 'col-{0}-{1}'.format(narrowest, column_width)
        }
        self.extend_children(obj, wanted_children, BootstrapColumnPlugin, child_glossary=child_glossary)

plugin_pool.register_plugin(BootstrapRowPlugin)


class BootstrapColumnPlugin(BootstrapPluginBase):
    name = _("Column")
    parent_classes = ('BootstrapRowPlugin',)
    alien_child_classes = True
    default_css_attributes = list(itertools.chain(*(('{}-column-width'.format(s),
        '{}-column-offset'.format(s), '{}-column-ordering'.format(s), '{}-responsive-utils'.format(s),)
        for s in BS3_BREAKPOINT_KEYS)))
    glossary_variables = ['container_max_widths']

    def get_form(self, request, obj=None, **kwargs):
        def chose_help_text(*phrases):
            if next_bp:
                return phrases[0].format(*BS3_BREAKPOINTS[next_bp])
            elif len(breakpoints) > 1:
                return phrases[1].format(*BS3_BREAKPOINTS[bp])
            else:
                return phrases[2]

        glossary_fields = []
        parent_obj, parent_plugin = self.parent.get_plugin_instance()
        units = [ungettext_lazy("{} unit", "{} units", i).format(i) for i in range(0, 13)]
        if isinstance(parent_plugin, BootstrapPluginBase):
            breakpoints = parent_obj.get_complete_glossary()['breakpoints']
            for bp in breakpoints:
                try:
                    next_bp = breakpoints[breakpoints.index(bp) + 1]
                    last = BS3_BREAKPOINT_KEYS.index(next_bp)
                except IndexError:
                    next_bp = None
                    last = None
                finally:
                    first = BS3_BREAKPOINT_KEYS.index(bp)
                    devices = ', '.join([force_text(BS3_BREAKPOINTS[b][2]) for b in BS3_BREAKPOINT_KEYS[first:last]])
                if breakpoints.index(bp) == 0:
                    # first breakpoint
                    choices = tuple(('col-{}-{}'.format(bp, i), units[i]) for i in range(1, 13))
                    label = _("Column width for {}").format(devices)
                    help_text = chose_help_text(
                        _("Number of column units for devices narrower than {} pixels."),
                        _("Number of column units for devices wider than {} pixels."),
                        _("Number of column units for all devices.")
                    )
                    glossary_fields.append(PartialFormField('{}-column-width'.format(bp),
                        widgets.Select(choices=choices),
                        initial='col-{}-12'.format(bp), label=label, help_text=help_text))
                else:
                    choices = (('', _("Inherit from above")),) + \
                        tuple(('col-{}-{}'.format(bp, i), units[i]) for i in range(1, 13))
                    label = _("Column width for {}").format(devices)
                    help_text = chose_help_text(
                        _("Override column units for devices narrower than {} pixels."),
                        _("Override column units for devices wider than {} pixels."),
                        _("Override column units for all devices.")
                    )
                    glossary_fields.append(PartialFormField('{}-column-width'.format(bp),
                        widgets.Select(choices=choices),
                        initial='', label=label, help_text=help_text))

                # handle offset
                if breakpoints.index(bp) == 0:
                    empty_offset_choice = _("No offset")
                    offset_range = range(1, 13)
                else:
                    empty_offset_choice = _("Inherit from above")
                    offset_range = range(0, 13)
                choices = (('', empty_offset_choice),) + \
                    tuple(('col-{}-offset-{}'.format(bp, i), units[i])
                          for i in offset_range)
                label = _("Offset for {}").format(devices)
                help_text = chose_help_text(
                    _("Number of offset units for devices narrower than {} pixels."),
                    _("Number of offset units for devices wider than {} pixels."),
                    _("Number of offset units for all devices.")
                )
                glossary_fields.append(PartialFormField('{}-column-offset'.format(bp),
                    widgets.Select(choices=choices), label=label, help_text=help_text))

                # handle column ordering using push/pull settings
                choices = (('', _("No reordering")),) + \
                    tuple(('col-{}-push-{}'.format(bp, i), _("Push {}").format(units[i])) for i in range(0, 12)) + \
                    tuple(('col-{}-pull-{}'.format(bp, i), _("Pull {}").format(units[i])) for i in range(0, 12))
                label = _("Column ordering for {0}").format(devices)
                help_text = chose_help_text(
                    _("Column ordering for devices narrower than {} pixels."),
                    _("Column ordering for devices wider than {} pixels."),
                    _("Column ordering for all devices.")
                )
                glossary_fields.append(PartialFormField('{}-column-ordering'.format(bp),
                    widgets.Select(choices=choices), label=label, help_text=help_text))

                # handle responsive utilies
                choices = (('', _("Default")), ('visible-{}'.format(bp), _("Visible")), ('hidden-{}'.format(bp), _("Hidden")),)
                label = _("Responsive utilities for {}").format(devices)
                help_text = chose_help_text(
                    _("Utility classes for showing and hiding content by devices narrower than {} pixels."),
                    _("Utility classes for showing and hiding content by devices wider than {} pixels."),
                    _("Utility classes for showing and hiding content for all devices.")
                )
                glossary_fields.append(PartialFormField('{}-responsive-utils'.format(bp),
                    widgets.RadioSelect(choices=choices), label=label, help_text=help_text, initial=''))
        glossary_fields = [
            glossary_fields[i + len(glossary_fields) // len(breakpoints) * j]
            for i in range(0, len(glossary_fields) // len(breakpoints))
            for j in range(0, len(breakpoints))
        ]
        kwargs.update(glossary_fields=glossary_fields)
        return super(BootstrapColumnPlugin, self).get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        super(BootstrapColumnPlugin, self).save_model(request, obj, form, change)
        obj.sanitize_children()

    @classmethod
    def sanitize_model(cls, obj):
        sanitized = super(BootstrapColumnPlugin, cls).sanitize_model(obj)
        parent_glossary = obj.get_parent_glossary()
        column_units = 12
        obj.glossary['container_max_widths'] = {}
        breakpoints = parent_glossary.get('breakpoints', [])
        for bp in BS3_BREAKPOINT_KEYS:
            width_key = '{0}-column-width'.format(bp)
            offset_key = '{0}-column-offset'.format(bp)
            if bp in breakpoints:
                width_val = obj.glossary.get(width_key, '').lstrip('col-{0}-'.format(bp))
                if width_val.isdigit():
                    column_units = int(width_val)
                new_width = parent_glossary['container_max_widths'][bp] * column_units / 12 - settings.CMSPLUGIN_CASCADE['bootstrap3']['gutter']
                if new_width != obj.glossary['container_max_widths'].get(bp):
                    obj.glossary['container_max_widths'][bp] = new_width
                    sanitized = True
            else:
                # remove obsolete entries from own glossary
                # If no breakpoints are set, the plugin is not inside a BootstrapContainerPlugin,
                # probably in the clipboard placeholder. Don't delete widths and offsets from the
                # glossary in this case, as we would otherwise lose this information.
                if breakpoints:
                    if width_key in obj.glossary:
                        del obj.glossary[width_key]
                        sanitized = True
                    if offset_key in obj.glossary:
                        del obj.glossary[offset_key]
                        sanitized = True
        return sanitized

    @classmethod
    def get_identifier(cls, obj):
        identifier = super(BootstrapColumnPlugin, cls).get_identifier(obj)
        glossary = obj.get_complete_glossary()
        widths = []
        for bp in glossary.get('breakpoints', []):
            width = obj.glossary.get('{0}-column-width'.format(bp), '').replace('col-{0}-'.format(bp), '')

            if width:
                widths.append(width)
        if len(widths) > 1:
            content = _('widths: {0} units').format(' / '.join(widths))
        elif len(widths) == 1:
            width = int(widths[0])
            content = ungettext_lazy('default width: {0} unit', 'default width: {0} units', width).format(width)
        else:
            content = _('unknown width')
        return format_html('{0}{1}', identifier, content)

plugin_pool.register_plugin(BootstrapColumnPlugin)
