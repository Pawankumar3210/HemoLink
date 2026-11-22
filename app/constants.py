"""Shared constants: controlled vocabularies used by models, forms and templates."""

BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")

ROLE_DONOR = "donor"
ROLE_RECIPIENT = "recipient"
ROLE_ADMIN = "admin"
ROLES = (ROLE_DONOR, ROLE_RECIPIENT, ROLE_ADMIN)
REGISTRATION_ROLES = (ROLE_DONOR, ROLE_RECIPIENT)

ACCOUNT_ACTIVE = "active"
ACCOUNT_SUSPENDED = "suspended"
ACCOUNT_DELETED = "deleted"
ACCOUNT_STATUSES = (ACCOUNT_ACTIVE, ACCOUNT_SUSPENDED, ACCOUNT_DELETED)

AVAILABLE = "available"
TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
UNAVAILABLE = "unavailable"
AVAILABILITY_STATUSES = (AVAILABLE, TEMPORARILY_UNAVAILABLE, UNAVAILABLE)

GENDERS = ("Female", "Male", "Other", "Prefer not to say")

URGENCY_NORMAL = "normal"
URGENCY_HIGH = "high"
URGENCY_URGENT = "urgent"
URGENCY_LEVELS = (URGENCY_NORMAL, URGENCY_HIGH, URGENCY_URGENT)

REQUEST_OPEN = "open"
REQUEST_FULFILLED = "fulfilled"
REQUEST_CANCELLED = "cancelled"
REQUEST_REJECTED = "rejected"
REQUEST_STATUSES = (
    REQUEST_OPEN,
    REQUEST_FULFILLED,
    REQUEST_CANCELLED,
    REQUEST_REJECTED,
)

CONTACT_PENDING = "pending"
CONTACT_ACCEPTED = "accepted"
CONTACT_DECLINED = "declined"
CONTACT_WITHDRAWN = "withdrawn"
CONTACT_STATUSES = (
    CONTACT_PENDING,
    CONTACT_ACCEPTED,
    CONTACT_DECLINED,
    CONTACT_WITHDRAWN,
)

MIN_DONOR_AGE = 18
MAX_DONOR_AGE = 65
MAX_UNITS_PER_REQUEST = 20

INDIAN_STATES = (
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)

LABELS = {
    AVAILABLE: "Available",
    TEMPORARILY_UNAVAILABLE: "Temporarily unavailable",
    UNAVAILABLE: "Unavailable",
    URGENCY_NORMAL: "Normal",
    URGENCY_HIGH: "High",
    URGENCY_URGENT: "Urgent",
    REQUEST_OPEN: "Open",
    REQUEST_FULFILLED: "Fulfilled",
    REQUEST_CANCELLED: "Cancelled",
    REQUEST_REJECTED: "Rejected",
    CONTACT_PENDING: "Pending",
    CONTACT_ACCEPTED: "Accepted",
    CONTACT_DECLINED: "Declined",
    CONTACT_WITHDRAWN: "Withdrawn",
    ACCOUNT_ACTIVE: "Active",
    ACCOUNT_SUSPENDED: "Suspended",
    ACCOUNT_DELETED: "Deleted",
    ROLE_DONOR: "Donor",
    ROLE_RECIPIENT: "Recipient",
    ROLE_ADMIN: "Administrator",
}


def sql_in(column, values):
    """Build a ``column IN ('a', 'b')`` fragment for CHECK constraints.

    Only ever called with the constant tuples above, never user input.
    """
    quoted = ", ".join("'%s'" % value for value in values)
    return "%s IN (%s)" % (column, quoted)
