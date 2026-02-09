"""
Loan Pipeline Report - Shows all loans by status for pipeline management
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "name",
            "label": _("Loan ID"),
            "fieldtype": "Link",
            "options": "Loan",
            "width": 120
        },
        {
            "fieldname": "borrower",
            "label": _("Borrower"),
            "fieldtype": "Link",
            "options": "Borrower",
            "width": 150
        },
        {
            "fieldname": "loan_product",
            "label": _("Product"),
            "fieldtype": "Link",
            "options": "Loan Product",
            "width": 120
        },
        {
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "workflow_state",
            "label": _("Workflow State"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "requested_amount",
            "label": _("Requested Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "approved_amount",
            "label": _("Approved Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "application_date",
            "label": _("Application Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "tenure_months",
            "label": _("Tenure (Months)"),
            "fieldtype": "Int",
            "width": 110
        },
        {
            "fieldname": "interest_rate",
            "label": _("Interest Rate %"),
            "fieldtype": "Float",
            "width": 110
        },
        {
            "fieldname": "loan_officer",
            "label": _("Loan Officer"),
            "fieldtype": "Link",
            "options": "User",
            "width": 150
        }
    ]


def get_data(filters):
    """Get loan pipeline data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT
            l.name,
            l.borrower,
            l.loan_product,
            l.branch,
            l.workflow_state,
            l.status,
            l.requested_amount,
            l.approved_amount,
            l.application_date,
            l.tenure_months,
            l.interest_rate,
            l.owner as loan_officer
        FROM
            `tabLoan` l
        WHERE
            l.docstatus < 2
            {conditions}
        ORDER BY
            l.application_date DESC
    """, filters, as_dict=1)
    
    return data


def get_conditions(filters):
    """Build filter conditions"""
    conditions = []
    
    if filters.get("company"):
        conditions.append("AND l.company = %(company)s")
    
    if filters.get("branch"):
        conditions.append("AND l.branch = %(branch)s")
    
    if filters.get("status"):
        conditions.append("AND l.status = %(status)s")
    
    if filters.get("workflow_state"):
        conditions.append("AND l.workflow_state = %(workflow_state)s")
    
    if filters.get("loan_product"):
        conditions.append("AND l.loan_product = %(loan_product)s")
    
    if filters.get("from_date"):
        conditions.append("AND l.application_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("AND l.application_date <= %(to_date)s")
    
    return " ".join(conditions)


def get_chart_data(data):
    """Generate chart data for loan pipeline"""
    status_count = {}
    
    for row in data:
        status = row.get("workflow_state") or row.get("status") or "Unknown"
        status_count[status] = status_count.get(status, 0) + 1
    
    return {
        "data": {
            "labels": list(status_count.keys()),
            "datasets": [
                {
                    "name": "Loans by Status",
                    "values": list(status_count.values())
                }
            ]
        },
        "type": "donut",
        "height": 300,
        "colors": ["#7cd6fd", "#ffbf00", "#ff6c5f", "#a7c5e7", "#5fe65f"]
    }
