import logging

from django.db import models
from django.apps import apps
from django.core.exceptions import ValidationError

from djangoapprove.settings import (
    APPROVAL_INITIAL_STATUS, APPROVAL_COMPLETED_STATUS,
    APPROVAL_STATUSES, APPROVAL_TRANSITIONS,
)


logger = logging.getLogger(__name__)


class Approval(models.Model):
    """
    Model to log and manage approval requests for CRUD operations.
    Stores details about the operation being done on a model instance.

    Expects said model to implement the `ApprovalMixin` mixin.
    """
    REQUEST_CREATE = 'create'
    REQUEST_SAVE = 'save'
    REQUEST_UPDATE = 'update'
    REQUEST_DELETE = 'delete'

    REQUEST_CHOICES = [
        (REQUEST_CREATE, 'Create'),
        (REQUEST_SAVE, 'Save'),
        (REQUEST_DELETE, 'Delete'),
    ]

    approval_id = models.AutoField(primary_key=True)
    unique_key = models.CharField(
        null=False,
        blank=False,
        max_length=100,
        help_text="Unique key for the model instance.",
        db_index=True,
    )
    model_name = models.CharField(
        null=True,
        blank=False,
        default=None,
        max_length=100,
        help_text="Name of the model on which the operation is being done.",
    )
    request_type = models.CharField(
        null=False,
        blank=False,
        max_length=10,
        choices=REQUEST_CHOICES,
        default=REQUEST_SAVE,
        help_text="Type of operation being done on the model.",
    )
    request_subtype = models.CharField(
        null=True,
        blank=True,
        max_length=100,
        help_text="Subtype of the operation being done on the model.",
    )
    data = models.JSONField(
        null=True,
        blank=False,
        default=None,
        help_text="JSON data for the operation payload.",
    )
    status = models.CharField(
        null=False,
        blank=False,
        max_length=10,
        choices=APPROVAL_STATUSES.items(),
        default=APPROVAL_INITIAL_STATUS,
        help_text="Current status of the approval request.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'approval'
        verbose_name = 'Approval'
        verbose_name_plural = 'Approvals'
        ordering = ['-created_at']

    def clean(self):
        """
        Custom validation logic before saving the instance.
        """
        super().clean()
        try:
            self.validate_data()
        except Exception as e:
            raise ValidationError from e

    @classmethod
    def get_next_status(cls, current_status: str, action: str):
        """
        Get the next status based on the current status and action.
        """
        return APPROVAL_TRANSITIONS.get(action, {}).get(current_status, None)

    def transition(self, action: str):
        """
        Transition the approval request to the next state based on the action.
        """
        next_status = self.get_next_status(self.status, action)
        if next_status is None:
            raise ValueError(f"Invalid action {action} for status {self.status}")

        self.status = next_status
        self.save()

        if self.status == APPROVAL_COMPLETED_STATUS:
            try:
                self.execute_request()
            except Exception as e:
                logger.error("execution failed for approval %s: %s", self.approval_id, e)
                self.status = 'FAILED'
                self.save()
                raise e
            else:
                logger.info("execution succeeded for approval %s", self.approval_id)

    def validate_data(self):
        """
        Validate that the required fields exist in the data.
        """
        if not self.data:
            raise ValueError("approval data is missing.")
        if self.request_type in [self.REQUEST_UPDATE, self.REQUEST_DELETE] and 'pk' not in self.data:
            raise ValueError(f"'pk' is required for {self.request_type} requests.")
        if self.request_type in [self.REQUEST_UPDATE] and not self.data:
            raise ValueError("data is required for save/update requests.")

    def _get_model_or_instance(self, primary_key=None):
        """
        Get the model class or a specific instance based on the primary key.
        """
        model = apps.get_model(self.model_name)
        if not model:
            raise ValueError(f"Model '{self.model_name}' does not exist.")
        if primary_key:
            instance = model.objects.filter(pk=primary_key).first()
            if not instance:
                raise ValueError(f"Instance with pk '{primary_key}' not found in model '{self.model_name}'.")
            return instance
        return model

    def _get_instance_data(self):
        """
        Get field data from the JSON payload.
        """
        return self.data.items()

    def _validate_fields(self, model, fields):
        """
        Validate that the fields exist on the model.
        """
        valid_fields = {field.name for field in model._meta.fields}
        for field in fields:
            if field not in valid_fields:
                raise ValueError(f"Field '{field}' is not valid for model '{self.model_name}'.")

    def _apply_field_value(self, instance, field, value):
        """
        Apply a value to a field, handling special cases like ManyToManyFields.
        """
        field_object = instance._meta.get_field(field)
        if isinstance(field_object, models.ManyToManyField):
            getattr(instance, field).set(value)
        else:
            setattr(instance, field, value)

    def _create_instance(self):
        """
        Create a new instance with the provided data.
        """
        model = self._get_model_or_instance()
        self._validate_fields(model, dict(self.data))
        instance = model()
        for field, value in self._get_instance_data():
            self._apply_field_value(instance, field, value)
        instance.direct_save()

    def _save_instance(self):
        """
        Save an existing instance with new field values.
        """
        model = self._get_model_or_instance()
        self._validate_fields(model, dict(self.data))
        instance = model()
        for field, value in self._get_instance_data():
            self._apply_field_value(instance, field, value)
        instance.direct_save()

    def _update_instance(self):
        """
        Update an existing model instance with new field values.
        """
        instance = self._get_model_or_instance(primary_key=self.data.pop('pk'))
        for field, value in self.data.items():
            setattr(instance, field, value)
        instance.direct_save()

    def _delete_instance(self):
        """
        Delete an existing instance.
        """
        instance = self._get_model_or_instance(primary_key=self.data.pop('pk'))
        instance.direct_delete()

    def execute_request(self):
        """
        Execute the action on the model instance based on the request type.
        """
        self.validate_data()
        if self.request_type == self.REQUEST_CREATE:
            self._create_instance()
        elif self.request_type == self.REQUEST_SAVE and self.request_subtype != self.REQUEST_UPDATE:
            self._save_instance()
        elif self.request_type == self.REQUEST_SAVE:
            self._update_instance()
        elif self.request_type == self.REQUEST_DELETE:
            self._delete_instance()
        else:
            raise ValueError(f"invalid request type: {self.request_type}")
