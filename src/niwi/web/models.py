# -*- coding: utf-8 -*-

from django.db import models
from django.conf import settings
from django.template.defaultfilters import slugify
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from niwi.utils import get_url_data, cacheable
from niwi.web.forms import LEXER_CHOICES
from niwi.contrib.db.fields import CreationDateTimeField, ModificationDateTimeField

import datetime, uuid

STATUS_CHOICES = (
    ('public', u'Public'),
    ('private', u'Private'),
    ('draft', u'Draft'),
)

def slugify_uniquely(value, model, slugfield="slug"):
    suffix = 0
    potential = base = slugify(value)
    if len(potential) == 0:
        potential = 'null'
    while True:
        if suffix:
            potential = "-".join([base, str(suffix)])
        if not model.objects.filter(**{slugfield: potential}).count():
            return potential
        suffix += 1


class Page(models.Model):
    slug  = models.SlugField(max_length=100, unique=True, db_index=True, editable=True, blank=True)
    title = models.CharField(max_length=500, db_index=True)
    content = models.TextField()
    markup = models.BooleanField(default=False)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, db_index=True, default='draft')
    owner = models.ForeignKey('auth.User', related_name='pages', null=True, default=None, blank=True)
    created_date = CreationDateTimeField(editable=True)
    modified_date = ModificationDateTimeField(editable=True)

    class Meta:
        db_table = 'pages'

    @models.permalink
    def get_absolute_url(self):
        return ('web:show-page', (), {'slug': self.slug})
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify_uniquely(self.title, self.__class__)

        super(Page, self).save(*args, **kwargs)

    def __unicode__(self):
        return u"Page: %s" % (self.title)


class Post(models.Model):
    slug  = models.SlugField(max_length=100, unique=True, db_index=True, editable=True, blank=True)
    title = models.CharField(max_length=500, db_index=True, blank=True)
    content = models.TextField()
    markup = models.BooleanField(default=False)
    owner = models.ForeignKey('auth.User', related_name='posts', null=True, default=None, blank=True)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, db_index=True, default='draft')
    tags = models.CharField(max_length=200, blank=True, null=True, default='', db_index=True)

    created_date = CreationDateTimeField(editable=True)
    modified_date = ModificationDateTimeField(editable=True)
    
    class Meta:
        db_table = 'posts'

    def __unicode__(self):
        return u"Post: %s" % (self.title) 

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify_uniquely(self.title, self.__class__)

        super(Post, self).save(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('web:show-post', (), {'slug': self.slug})


class PostAttachment(models.Model):
    post = models.ForeignKey('Post', related_name='attachments')
    slug = models.SlugField(max_length=200, unique=True, db_index=True, editable=True, blank=True)
    name = models.CharField(max_length=500, db_index=True, blank=True)
    file = models.FileField(max_length=500, upload_to="attachments/%Y/%m/%d",
        serialize=False, editable=True, blank=True)


class Bookmark(models.Model):
    title = models.CharField(max_length=500, blank=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True, editable=True, blank=True)
    url = models.CharField(max_length=1000, db_index=True)
    tags = models.CharField(max_length=1000, db_index=True, blank=True, default='')
    owner = models.ForeignKey('auth.User', related_name='bookmarks', blank=True, null=True)
    
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True)
    
    public = models.BooleanField(default=True)

    def __unicode__(self):
        return u"Bookmark: %s" % (self.title)

    class Meta:
        db_table = 'bookmarks'

    def save(self, *args, **kwargs):
        if not self.title:
            self.title, body = get_url_data(self.url)
        if not self.slug:
            self.slug = slugify_uniquely(self.title, self.__class__)
        super(Bookmark, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.slug

    @models.permalink
    def get_absolute_url(self):
        return ('web:show-bookmark', (), {'slug': self.slug})


class Paste(models.Model):
    text = models.TextField()
    lexer = models.CharField(max_length=5)
    title = models.CharField(max_length=100, blank=True)
    group = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"Paste: %s" % (self.title)

    class Meta:
        db_table = 'paste'

