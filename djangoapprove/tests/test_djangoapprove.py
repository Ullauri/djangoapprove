import unittest
import random
from importlib import reload

from django.db import models
from django.test import TestCase, override_settings
from djangoapprove.tests import DummyModelWithApproval
from djangoapprove.models import Approval
from djangoapprove.mixins import ApprovalMixin
from djangoapprove import settings

class DjangoApproveTestCase(TestCase):
    def setUp(self):
        Approval.objects.all().delete()
        DummyModelWithApproval.objects.all().delete()

    def test_save_creates_approval_request(self):
        """
        Test that saving a model instance creates an approval request.
        """
        value = random.randint(1, 1000)

        dummy_instance = DummyModelWithApproval(name="Test Name", value=value)
        dummy_instance.save()

        self.assertEqual(len(DummyModelWithApproval.objects.filter(value=value)), 0)
        self.assertEqual(Approval.objects.count(), 1)
        approval_request = Approval.objects.first()
        self.assertEqual(approval_request.model_name, "djangoapprove.DummyModelWithApproval")
        self.assertEqual(approval_request.request_type, Approval.REQUEST_SAVE)
        self.assertEqual(approval_request.status, "PENDING")

    def test_create_creates_approval_request(self):
        """
        Test that creating a model instance through the create method creates an approval request.
        """
        value = random.randint(1, 1000)

        dummy_instance = DummyModelWithApproval()
        approval_request = dummy_instance.create(name="New Instance", value=value)

        self.assertEqual(len(DummyModelWithApproval.objects.filter(value=value)), 0)
        self.assertEqual(Approval.objects.count(), 1)
        self.assertEqual(approval_request.model_name, "djangoapprove.DummyModelWithApproval")
        self.assertEqual(approval_request.request_type, Approval.REQUEST_CREATE)
        self.assertEqual(approval_request.request_subtype, None)
        self.assertEqual(approval_request.status, "PENDING")

    def test_update_creates_approval_request(self):
        """
        Test that updating a model instance creates an approval request.
        """
        value = random.randint(1, 1000)

        create_approval = DummyModelWithApproval.objects.create(name="Test Name", value=value)
        self.assertIsNotNone(create_approval)

        self.assertEqual(DummyModelWithApproval.objects.filter(value=value).count(), 0)
        create_approval.transition('APPROVE')

        dummy_instance = DummyModelWithApproval.objects.get(value=value)
        self.assertIsNotNone(dummy_instance)

        dummy_instance.name = "Updated Name"
        dummy_instance.save()

        self.assertEqual(Approval.objects.count(), 2)
        update_approval = Approval.objects.order_by('created_at').last()
        self.assertEqual(update_approval.model_name, "djangoapprove.DummyModelWithApproval")
        self.assertEqual(update_approval.request_type, Approval.REQUEST_SAVE)
        self.assertEqual(update_approval.request_subtype, Approval.REQUEST_UPDATE)

        update_approval.transition('APPROVE')

        dummy_instance = DummyModelWithApproval.objects.get(value=value)
        self.assertIsNotNone(dummy_instance)
        self.assertEqual(dummy_instance.name, "Updated Name")

    def test_delete_creates_approval_request(self):
        """
        Test that deleting a model instance creates an approval request.
        """
        value = random.randint(1, 1000)

        create_approval = DummyModelWithApproval.objects.create(name="Test Name", value=value)
        self.assertIsNotNone(create_approval)
        create_approval.transition('APPROVE')

        dummy_instance = DummyModelWithApproval.objects.get(value=value)
        self.assertIsNotNone(dummy_instance)

        dummy_instance.delete()
        self.assertEqual(Approval.objects.count(), 2)
        delete_approval = Approval.objects.order_by('created_at').last()

        self.assertEqual(delete_approval.model_name, "djangoapprove.DummyModelWithApproval")
        self.assertEqual(delete_approval.request_type, Approval.REQUEST_DELETE)
        self.assertEqual(delete_approval.request_subtype, None)

        delete_approval.transition('APPROVE')

        with self.assertRaises(DummyModelWithApproval.DoesNotExist):
            DummyModelWithApproval.objects.get(value=value)

    def test_prevent_duplicate_approval_requests(self):
        """
        Test that duplicate approval requests for the same operation are not allowed.
        """
        create_approval = DummyModelWithApproval.objects.create(name="Test Name", value=42)
        self.assertIsNotNone(create_approval)
        with self.assertRaises(ValueError):
            DummyModelWithApproval.objects.create(name="Test Name", value=42)

    def test_completed_approval_prevents_recreation(self):
        """
        Test that completed approval requests prevent recreation from new approvals.
        """
        create_approval = DummyModelWithApproval.objects.create(name="Test Name", value=42)
        self.assertIsNotNone(create_approval)
        create_approval.transition('APPROVE')
        with self.assertRaises(ValueError):
            create_approval.transition('APPROVE')

    def test_validate_data_missing_pk_for_update(self):
        """
        Test that an error is raised when a request is missing the `pk` field for an update request.
        """
        approval = Approval(
            model_name="djangoapprove.DummyModelWithApproval",
            request_type=Approval.REQUEST_UPDATE,
            data={},  # missing `pk`
        )
        with self.assertRaises(ValueError):
            approval.validate_data()

    def test_invalid_status_transition(self):
        """
        Test that an error is raised when an invalid status transition is attempted.
        """
        approval = Approval.objects.create(
            model_name="djangoapprove.DummyModelWithApproval",
            request_type=Approval.REQUEST_SAVE,
            status="PENDING",
            data={"name": "Invalid Transition Test"},
        )
        with self.assertRaises(ValueError):
            approval.transition("INVALID_ACTION")


    def test_model_not_found(self):
        """
        Test that an error is raised when the model is not found.
        """
        approval = Approval(
            model_name="djangoapprove.NonExistentModel",
            request_type=Approval.REQUEST_SAVE,
            data={"name": "Test Name", "value": 42},
        )
        with self.assertRaises(Exception):
            approval._get_model_or_instance()

    def test_execute_request_invalid_type(self):
        """
        Test that an error is raised when an invalid request type is provided.
        """
        approval = Approval.objects.create(
            model_name="djangoapprove.DummyModelWithApproval",
            request_type="INVALID_TYPE",
            data={"name": "Invalid Request Type Test"},
        )
        with self.assertRaises(ValueError):
            approval.execute_request()

    def test_direct_save_bypasses_approval(self):
        """
        Test that direct_save bypasses the approval process
        """
        dummy_instance = DummyModelWithApproval(name="Direct Save Test", value=123)
        dummy_instance.direct_save()

        self.assertEqual(DummyModelWithApproval.objects.count(), 1)
        self.assertEqual(Approval.objects.count(), 0)

    def test_direct_delete_bypasses_approval(self):
        """
        Test that direct_delete bypasses the approval process
        """
        dummy_instance = DummyModelWithApproval(name="Direct Save Test", value=123)
        dummy_instance.direct_save()
        dummy_instance.direct_delete()
        self.assertEqual(DummyModelWithApproval.objects.count(), 0)
        self.assertEqual(Approval.objects.count(), 0)

    def test_get_unique_key_not_implemented(self):
        """
        Test that an error is raised when get_unique_key is not implemented on the model.
        """
        class IncompleteModel(ApprovalMixin, models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "djangoapprove"

        incomplete_instance = IncompleteModel(name="Test Name")
        with self.assertRaises(NotImplementedError):
            incomplete_instance.get_unique_key()

    def test_execute_request_logs_error(self):
        """
        Test that an error is logged when an approval request execution fails.
        """
        approval = Approval.objects.create(
            model_name="djangoapprove.DummyModelWithApproval",
            request_type=Approval.REQUEST_SAVE,
            status="PENDING",
            data={"name": "Log Test"},  # missing required fields
        )
        with self.assertLogs("djangoapprove", level="ERROR") as log:
            with self.assertRaises(Exception):
                approval.transition("APPROVE")
        self.assertIn("Execution failed for approval", log.output[0])


class ApprovalSettingsTestCase(TestCase):
    @override_settings(
        APPROVAL_STATUSES={
            'WAITING': 'Waiting',
            'AUTHORIZED': 'Authorized',
            'REJECTED': 'Rejected',
            'FAILED': 'Failed',
        },
        APPROVAL_ACTIONS={
            'APPROVE': 'Authorize',
            'REJECT': 'Deny',
        },
        APPROVAL_TRANSITIONS={
            'APPROVE': {'WAITING': 'AUTHORIZED'},
            'REJECT': {'WAITING': 'REJECTED'},
        },
        APPROVAL_INITIAL_STATUS='WAITING',
        APPROVAL_COMPLETED_STATUS='AUTHORIZED',
    )
    def test_custom_settings(self):
        """
        Test custom statuses, actions, and transitions together.
        """
        reload(settings)

        # Verify custom statuses
        self.assertIn('WAITING', settings.APPROVAL_STATUSES)
        self.assertIn('AUTHORIZED', settings.APPROVAL_STATUSES)
        self.assertEqual(settings.APPROVAL_STATUSES['WAITING'], 'Waiting')
        self.assertEqual(settings.APPROVAL_STATUSES['AUTHORIZED'], 'Authorized')

        # Verify custom actions
        self.assertIn('APPROVE', settings.APPROVAL_ACTIONS)
        self.assertEqual(settings.APPROVAL_ACTIONS['APPROVE'], 'Authorize')
        self.assertIn('REJECT', settings.APPROVAL_ACTIONS)
        self.assertEqual(settings.APPROVAL_ACTIONS['REJECT'], 'Deny')

        # Verify custom transitions
        self.assertIn('APPROVE', settings.APPROVAL_TRANSITIONS)
        self.assertIn('WAITING', settings.APPROVAL_TRANSITIONS['APPROVE'])
        self.assertEqual(settings.APPROVAL_TRANSITIONS['APPROVE']['WAITING'], 'AUTHORIZED')

        # Verify initial and completed statuses
        self.assertEqual(settings.APPROVAL_INITIAL_STATUS, 'WAITING')
        self.assertEqual(settings.APPROVAL_COMPLETED_STATUS, 'AUTHORIZED')

    @override_settings(
        APPROVAL_STATUSES={
            'PENDING': 'Pending',
            'APPROVED': 'Approved',
            'FAILED': 'Failed',
        },
        APPROVAL_COMPLETED_STATUS='INVALID',
    )
    def test_invalid_completed_status(self):
        """
        Test that invalid completed status raises an error.
        """
        with self.assertRaises(ValueError):
            reload(settings)

    @override_settings(
        APPROVAL_STATUSES={
            'PENDING': 'Pending',
            'APPROVED': 'Approved',
            'FAILED': 'Failed',
        },
        APPROVAL_INITIAL_STATUS='INVALID',
    )
    def test_invalid_initial_status(self):
        """
        Test that invalid initial status raises an error.
        """
        with self.assertRaises(ValueError):
            reload(settings)

    @override_settings(
        APPROVAL_TRANSITIONS={
            'APPROVE': {'INVALID': 'APPROVED'},
        },
    )
    def test_invalid_transition_status(self):
        """
        Test that invalid transition status raises an error.
        """
        with self.assertRaises(ValueError):
            reload(settings)


if __name__ == "__main__":
    unittest.main()
