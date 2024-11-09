# djangoapprove

djangoapprove is a Django module that manages approval workflows for CRUD operations on Django models. It allows interception of model operations (create, update, delete) and introduces a customizable approval flow before the changes are applied.

## Features
- **Approval Workflow**: Intercepts CRUD operations and creates approval requests.
- **Approval Types**: Supports creation, updates, and deletions.
- **Direct Operations**: Allows bypassing approval for direct operations.

## Installation

1. Install using `pip`:
   ```bash
   pip install djangoapprove
   ```
2. Add `djangoapprove` to your `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...,
    'djangoapprove',
]
```
3. Run migrations to create the Approval model table:
```bash
python manage.py makemigrations djangoapprove
python manage.py migrate
```

## Usage

### Basic Integration
To integrate `djangoapprove` with a model, use the `ApprovalMixin` and the `ApprovalManager`:
```python
from django.db import models
from djangoapprove.mixins import ApprovalMixin, ApprovalManager

class MyModel(ApprovalMixin, models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    objects = ApprovalManager() # or approval_objects = ApprovalManager for MyModel.approval_objects.create

    def get_unique_key(self):
        return f"mymodel-{self.pk or some_unique_property}"
```

---
### Approving Requests

Once an operation is intercepted, it creates an Approval record. Approvals can be reviewed and transitioned to the next state (e.g., APPROVED).

```python
from djangoapprove.models import Approval

# Approve a pending request
approval = Approval.objects.get(pk=1)
approval.transition("APPROVE")
```

---
### Settings

You can customize states, transitions, and initial/completed statuses in your `settings.py`:

```python
APPROVAL_ACTIONS = {
    "APPROVE": "Approve",
    "REJECT": "Reject",
}

APPROVAL_STATUSES = {
    "PENDING": "Pending",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
    "FAILED": "Failed",
}

APPROVAL_TRANSITIONS = {
    "APPROVE": {"PENDING": "APPROVED"}, # Applying APPROVE to PENDING results in APPROVED
    "REJECT": {"PENDING": "REJECTED"}, # Applying REJECT to PENDING results in REJECTED
}

APPROVAL_INITIAL_STATUS = "PENDING"
APPROVAL_COMPLETED_STATUS = "APPROVED"
```

---

### Example: Approval Workflow

1. Intercept Save Operation:
```python
instance = MyModel(name="Example", description="This is a test.")
approval = instance.save()  # Does not save immediately
```

2. Review The Approval:
```python
# Fetch the pending approval
approval = Approval.objects.filter(unique_key='Example').first()
print(approval.data)  # View the data payload
```

3. Approve The Request:
```python
approval.transition("APPROVE")
```

4. Verify Execution:
```python
# The instance should now be created
instance = MyModel.objects.get(name="Example")
```

### Direct Operations (Bypassing Approval)
If you need to bypass the approval process (e.g., for admin operations), you can use the direct_save and direct_delete methods:
```python
instance = MyModel(name="Direct Save Example", value=123)
instance.direct_save()
instance.direct_delete()
```
