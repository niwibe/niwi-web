# -*- coding: utf-8 -*-
from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_str, force_unicode
from django.utils.safestring import mark_safe
from django.template import loader

from niwi.utils import Singleton
from niwi.utils import cacheable

from django_dbconf.conf import config

register = template.Library()


@register.filter(name="markdown")
def markdown(value, arg=''):
    try:
        from niwi.contrib.markdown2 import markdown
    except ImportError:
        if settings.DEBUG:
            raise template.TemplateSyntaxError("Error in {% markdown %} filter: The Python markdown library isn't installed.")
        return force_unicode(value)
    else:
        extensions = {'code-color':{'style':'trac'}}
        return mark_safe(markdown(force_unicode(value), extras=extensions))

markdown.is_safe = True

@register.filter(name="fixname")
def correct_filename(name):
    return name.rsplit("/",1)[-1]


class HomePageNode(template.Node):
    def __init__(self):
        self.home_page = config.get('core.homepage', '')

    def render_filepaste(self, context):
        key, pageslug = None, None
        if len(self.home_page.split(",")) == 2:
            pageslug = self.home_page.split(",")[1]
            
        from niwi_apps.filepaste.models import WebFile
        context = {
            'files': WebFile.objects.filter(hidden=False).order_by('-created_date')[:50],
            'pageslug': pageslug,
        }
        template_name = "%s/filepaste_page.html" % (settings.TEMPLATES_THEME)
        return mark_safe(loader.render_to_string(template_name, context))

    def render_page(self, context):
        from niwi.web.models import Page
        try:
            page = Page.objects.get(slug=self.home_page)
        except Page.DoesNotExist:
            return mark_safe(u"")
    
        context = {
            'hpage':page.content,
            'markup':page.markup
        }
        template_name = "%s/utils/homepage.html" % (settings.TEMPLATES_THEME)
        return mark_safe(loader.render_to_string(template_name, context))
    
    @cacheable("%(home_page)s_homepagenode", timeout=30)
    def render(self, context):
        if 'filepaste' in self.home_page:
            return self.render_filepaste(context)
        else:
            return self.render_page(context)


@register.tag(name="homepage")
def homepage(parser, token):
    return HomePageNode()


class AnalyticsNode(template.Node):
    """ 
    Analytics singleton Node. 
    """

    def __init__(self):
        self.enabled = False
        self.analytics_code = config.get('google.analytics.code')
        self.analytics_domain = config.get('google.analytics.domain')

        if self.analytics_code:
            self.enabled = True

    def render(self, context):
        if self.enabled:
            context.update({'code': self.analytics_code, 'domain': self.analytics_domain})
            return template.loader.render_to_string(
                "%s/utils/analytics.html" % (settings.TEMPLATES_THEME), context)
        else:
            return ''


@register.tag(name="analytics")
def analytics_tag(parser, token):
    return AnalyticsNode()



class ShowPageNode(template.Node):
    """ 
    Show and render page node.
    """

    def __init__(self, pagename):
        self.pagename = pagename
    
    @cacheable("%(pagename)s", timeout=30)
    def render(self, context):
        pagename = self.pagename.resolve(context)
        from niwi.web.models import Page
        try:
            page = Page.objects.get(slug=pagename)
        except Page.DoesNotExist:
            return mark_safe('')
        
        t = template.Template(page.content)
        result = t.render(context)
        return mark_safe(result)


@register.tag(name="show_page")
def show_page(parser, token):
    """ 
    Render litle block obtaingin source from dinamicaly
    writed on Page model. 
    """
    try:
        tag_name, page_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
    return ShowPageNode(parser.compile_filter(page_name))


class TemplateNode(template.Node):
    def __init__(self, obj):
        self.obj = obj

    def render(self, context):
        obj = self.obj.resolve(context)

        t = template.Template(obj.content)
        content = t.render(template.Context(context))

        if obj.markup:
            from niwi.contrib.markdown2 import markdown
            extensions = {'code-color':{'style':'trac'}}
            content = markdown(force_unicode(content), extras=extensions)

        return mark_safe(content)


@register.tag(name="render_page_as_template")
def render_tmpl(parser, token):
    """
    Renders model objects content as template.
    """

    try:
        tag_name, obj = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % \
                                        token.contents.split()[0])

    obj = parser.compile_filter(obj)
    return TemplateNode(obj)


@register.filter(name="parse_tags")
def parse_tags(value):
    split = None if "," not in value else ","
    tags = [tag.strip() for tag in value.split(split)]
    tags_html = ['<a href="%s">%s</a>' % \
        (reverse('web:posts', kwargs={'tag':tagname}), tagname) for tagname in tags]
    return mark_safe(", ".join(tags_html))


class PostFileLinkNode(template.Node):
    def __init__(self, slug):
        self.slug = slug

    
    def get_attachment(self, context):
        slug = self.slug.resolve(context)
        from niwi.web.models import PostAttachment

        try:
            attachment = PostAttachment.objects.get(slug=slug)
        except PostAttachment.DoesNotExist:
            return None
            
        return attachment

    @cacheable("%(slug)s_post_file_link", timeout=30)
    def render(self, context):
        attachment = self.get_attachment(context)
        return mark_safe(attachment.file.url)
        

class PostFileLinkTagNode(PostFileLinkNode):
    def render(self, context):
        attachment = self.get_attachment(context)
        return mark_safe("<a href='{0}' class='post-file-link'>{1}</a>".format(
            attachment.file.url, 
            attachment.name
        ))


@register.tag(name='post_file_link')
def post_file_link(parser, token):
    try:
        tag_name, slug = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % \
                                        token.contents.split()[0])

    slug = parser.compile_filter(slug)
    return PostFileLinkTagNode(slug)


@register.tag(name='post_file_url')
def post_file_url(parser, token):
    try:
        tag_name, slug = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % \
                                        token.contents.split()[0])

    slug = parser.compile_filter(slug)
    return PostFileLinkNode(slug)
