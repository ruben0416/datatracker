# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models
from redesign.name.models import *
from redesign.person.models import Email, Person

import datetime

class GroupInfo(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)
    name = models.CharField(max_length=80)
    acronym = models.CharField(max_length=16, blank=True, db_index=True)
    state = models.ForeignKey(GroupStateName, null=True)
    type = models.ForeignKey(GroupTypeName, null=True)
    parent = models.ForeignKey('Group', blank=True, null=True)
    ad = models.ForeignKey(Person, blank=True, null=True)
    list_email = models.CharField(max_length=64, blank=True)
    list_subscribe = models.CharField(max_length=255, blank=True)
    list_archive = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)
    def __unicode__(self):
        return self.name

    class Meta:
        abstract = True

class Group(GroupInfo):
    # we keep charter separate
    charter = models.OneToOneField('doc.Document', related_name='chartered_group', blank=True, null=True)
    
    def latest_event(self, *args, **filter_args):
        """Get latest group event with filter arguments, e.g.
        d.latest_event(type="xyz")."""
        e = GroupEvent.objects.filter(group=self).filter(**filter_args).order_by('-time', '-id')[:1]
        return e[0] if e else None
    
# This will record the new state and the date it occurred for any changes
# to a group.  The group acronym must be unique and is the invariant used
# to select group history from this table.
class GroupHistory(GroupInfo):
    group = models.ForeignKey(Group, related_name='history_set')
    
    class Meta:
        verbose_name_plural="group histories"

def save_group_in_history(group):
    def get_model_fields_as_dict(obj):
        return dict((field.name, getattr(obj, field.name))
                    for field in obj._meta.fields
                    if field is not obj._meta.pk)

    # copy fields
    fields = get_model_fields_as_dict(group)
    del fields["charter"] # Charter is saved canonically on Group
    fields["group"] = group
    
    grouphist = GroupHistory(**fields)
    grouphist.save()

    # save RoleHistory
    for role in group.role_set.all():
        rh = RoleHistory(name=role.name, group=grouphist, email=role.email)
        rh.save()

    # copy many to many
    for field in group._meta.many_to_many:
        if not field.rel.through:
            # just add the attributes
            rel = getattr(grouphist, field.name)
            for item in getattr(group, field.name).all():
                rel.add(item)

    return grouphist

class GroupURL(models.Model):
    group = models.ForeignKey(Group)
    name = models.CharField(max_length=255)
    url = models.URLField(verify_exists=False)

class GroupMilestone(models.Model):
    group = models.ForeignKey(Group)
    desc = models.TextField()
    expected_due_date = models.DateField()
    done = models.BooleanField()
    done_date = models.DateField(null=True, blank=True)
    time = models.DateTimeField(auto_now=True)
    def __unicode__(self):
	return self.desc[:20] + "..."
    class Meta:
	ordering = ['expected_due_date']

GROUP_EVENT_CHOICES = [
    # core events
    ("proposed", "Proposed group"),
    ("started", "Started group"),
    ("concluded", "Concluded group"),

    # misc group events
    ("added_comment", "Added comment"),
    ("info_changed", "Changed WG metadata"),
    ]
    
class GroupEvent(models.Model):
    """An occurrence for a group, used for tracking who, when and what."""
    group = models.ForeignKey(Group)
    time = models.DateTimeField(default=datetime.datetime.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=GROUP_EVENT_CHOICES)
    by = models.ForeignKey(Person)
    desc = models.TextField()

    def __unicode__(self):
        return u"%s %s at %s" % (self.by.name, self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', 'id']

class Role(models.Model):
    name = models.ForeignKey(RoleName)
    group = models.ForeignKey(Group)
    email = models.ForeignKey(Email, help_text="Email address used by person for this role")
    auth = models.CharField(max_length=255, blank=True) # unused?
    def __unicode__(self):
        return u"%s is %s in %s" % (self.email.get_name(), self.name.name, self.group.acronym)

    
class RoleHistory(models.Model):
    # RoleHistory doesn't have a time field as it's not supposed to be
    # used on its own - there should always be a GroupHistory
    # accompanying a change in roles, so lookup the appropriate
    # GroupHistory instead
    name = models.ForeignKey(RoleName)
    group = models.ForeignKey(GroupHistory)
    email = models.ForeignKey(Email, help_text="Email address used by person for this role")
    auth = models.CharField(max_length=255, blank=True) # unused?
    def __unicode__(self):
        return u"%s is %s in %s" % (self.email.get_name(), self.name.name, self.group.acronym)
