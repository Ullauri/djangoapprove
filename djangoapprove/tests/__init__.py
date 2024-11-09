import django

from django.db import models
from django.conf import settings
from django.apps import apps
from django.db import connection
from django.core.management import call_command

settings.configure(
    INSTALLED_APPS=[
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'djangoapprove',
        'djangoapprove.tests',
    ],
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',  # in-memory database for testing
        }
    },
    SECRET_KEY="dummy-secret-key",
)

django.setup()
call_command('migrate')

from djangoapprove.models import Approval
from djangoapprove.mixins import ApprovalMixin, ApprovalManager


class DummyModelWithApproval(ApprovalMixin, models.Model):
    """
    Dummy model to test ApprovalMixin functionality.
    """
    name = models.CharField(max_length=100)
    value = models.IntegerField()

    objects = ApprovalManager()

    class Meta:
        app_label = "djangoapprove"

    def get_unique_key(self):
        """
        Return a unique key for the dummy instance.
        """
        return f"{self.__class__.__name__}-{self.pk if self.pk else 'new'}"


# Create the table for DummyModel
with connection.schema_editor() as schema_editor:
    schema_editor.create_model(Approval)
    schema_editor.create_model(DummyModelWithApproval)
