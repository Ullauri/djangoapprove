import json

from django.db import models
from django.core.serializers import serialize

from djangoapprove.settings import (
    APPROVAL_COMPLETED_STATUS,
)
from djangoapprove.models import Approval


class ApprovalManager(models.Manager):
    """
    ApprovalManager allows for the interception of Manager based operations such as `create`.
    """
    def create(self, **kwargs):
        """
        Override the default create method to use the mixin's save logic.
        """
        instance = self.model()

        request_type = Approval.REQUEST_CREATE
        request_subtype = None
        unique_key = instance.get_unique_key()

        instance.validate_existing_approval(request_type, request_subtype)

        approval = Approval.objects.create(
            model_name=instance._meta.label,
            request_type=request_type,
            request_subtype=request_subtype,
            unique_key=unique_key,
            data=kwargs,
        )

        return approval


class ApprovalMixin:
    """
    Mixin to intercept Model operations and introduce an Approval flow.
    """

    def get_unique_key(self):
        """
        Get a unique key for the model instance.
        """
        raise NotImplementedError("Method get_unique_key must be implemented.")

    def validate_existing_approval(self, request_type, request_subtype, *args, **kwargs):
        """
        Validate if there is an existing Approval request for the model instance.
        """
        # check if there is already an Approval request for this request
        approval = Approval.objects.filter(
            unique_key=self.get_unique_key(),
            model_name=self._meta.label,
            request_type=request_type,
            request_subtype=request_subtype,
        ).first()

        if approval is not None:
            if approval.status == APPROVAL_COMPLETED_STATUS:
                raise ValueError("approval request already completed.")
            else:
                raise ValueError(
                    f"approval request still in progress; current status: {approval.status}"
                )

    def create(self, **kwargs):
        """
        Intercept the create operation and create an approval request.
        """
        request_type = Approval.REQUEST_CREATE
        request_subtype = None
        unique_key = self.get_unique_key()

        self.validate_existing_approval(request_type, request_subtype)

        approval = Approval.objects.create(
            model_name=self._meta.label,
            request_type=request_type,
            request_subtype=request_subtype,
            unique_key=unique_key,
            data=dict(kwargs),
        )

        return approval

    def save(self, *args, **kwargs):
        """
        Intercept the save operation and create an approval request.
        """
        data = self.serialize_instance(self)

        request_subtype = None
        if self.pk is not None:
            data['pk'] = self.pk
            request_subtype = Approval.REQUEST_UPDATE

        self.validate_existing_approval(Approval.REQUEST_SAVE, request_subtype)

        approval = Approval.objects.create(
            model_name=self._meta.label,
            unique_key=self.get_unique_key(),
            request_type=Approval.REQUEST_SAVE,
            request_subtype=request_subtype,
            data=data,
        )

        return approval

    def delete(self, *args, **kwargs):
        """
        Intercept the delete operation and create an approval request.
        """
        self.validate_existing_approval(Approval.REQUEST_DELETE, None)

        data = self.serialize_instance(self)
        data['pk'] = self.pk

        approval = Approval.objects.create(
            model_name=self._meta.label,
            unique_key=self.get_unique_key(),
            request_type=Approval.REQUEST_DELETE,
            request_subtype=None,
            data=data,
        )

        return approval

    def direct_save(self, *args, **kwargs):
        """
        Directly save the model instance without creating an approval request.
        """
        super().save(*args, **kwargs)

    def direct_delete(self, *args, **kwargs):
        """
        Directly delete the model instance without creating an approval request.
        """
        super().delete(*args, **kwargs)

    def serialize_instance(self, instance):
        """
        Serialize a single model instance to JSON.
        """
        return json.loads(serialize('json', [instance]))[0]['fields']
