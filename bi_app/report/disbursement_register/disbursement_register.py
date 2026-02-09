"""
Disbursement Register Report - Records of all loan disbursements
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    chart = get_chart_data(data)
    
    return columns, data, None, chart, summary


def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "name",
            "label": _("Disbursement ID"),
            "fieldtype": "Link",
            "options": "Loan Disbursement",
            "width": 140
        },
        {
            "fieldname": "loan",
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
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120
        },
        {
            "fieldname": "loan_product",
            "label": _("Product"),
            "fieldtype": "Link",
            "options": "Loan Product",
            "width": 120
        },
        {
            "fieldname": "disbursement_date",
            "label": _("Disbursement Date"),
            "fieldtype": "Date",
            "width": 130
        },
        {
            "fieldname": "disbursed_amount",
            "label": _("Disbursed Amount"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "bank_account",
            "label": _("Bank Account"),
            "fieldtype": "Link",
            "options": "Account",
            "width": 180
        },
        {
            "fieldname": "mode_of_payment",
            "label": _("Payment Mode"),
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 130
        },
        {
            "fieldname": "reference_number",
            "label": _("Reference"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "tenure_months",
            "label": _("Tenure"),
            "fieldtype": "Int",
            "width": 80
        },
        {
            "fieldname": "interest_rate",
            "label": _("Rate %"),
            "fieldtype": "Float",
            "width": 80
        }
    ]


def get_data(filters):
    """Get disbursement register data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT
            ld.name,
            ld.loan,
            ld.borrower,
            l.branch,
            l.loan_product,
            ld.disbursement_date,
            ld.disbursed_amount,
            ld.bank_account,
            ld.mode_of_payment,
            ld.reference_number,
            ld.status,
            l.tenure_months,
            l.interest_rate
        FROM
            `tabLoan Disbursement` ld
        JOIN
            `tabLoan` l ON l.name = ld.loan
        WHERE
            ld.docstatus = 1
            {conditions}
        ORDER BY
            ld.disbursement_date DESC
    """, filters, as_dict=1)
    
    return data


def get_conditions(filters):
    """Build filter conditions"""
    conditions = []
    
    if filters.get("company"):
        conditions.append("AND ld.company = %(company)s")
    
    if filters.get("branch"):
        conditions.append("AND l.branch = %(branch)s")
    
    if filters.get("borrower"):
        conditions.append("AND ld.borrower = %(borrower)s")
    
    if filters.get("loan_product"):
        conditions.append("AND l.loan_product = %(loan_product)s")
    
    if filters.get("from_date"):
        conditions.append("AND ld.disbursement_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("AND ld.disbursement_date <= %(to_date)s")
    
    return " ".join(conditions)


def get_summary(data):
    """Calculate disbursement summary"""
    total_disbursed = sum(flt(row.get("disbursed_amount")) for row in data)
    total_count = len(data)
    
    avg_disbursement = total_disbursed / total_count if total_count > 0 else 0
    
    return [
        {
            "value": total_count,
            "indicator": "Blue",
            "label": _("Total Disbursements"),
            "datatype": "Int"
        },
        {
            "value": total_disbursed,
            "indicator": "Green",
            "label": _("Total Amount"),
            "datatype": "Currency"
        },
        {
            "value": avg_disbursement,
            "indicator": "Blue",
            "label": _("Average Disbursement"),
            "datatype": "Currency"
        }
    ]


def get_chart_data(data):
    """Generate disbursement trend chart"""
    # Group by month
    month_data = {}
    
    for row in data:
        disbursement_date = row.get("disbursement_date")
        if disbursement_date:
            month_key = disbursement_date.strftime("%Y-%m")
            month_data[month_key] = month_data.get(month_key, 0) + flt(row.get("disbursed_amount"))
    
    # Sort by month
    sorted_months = sorted(month_data.keys())
    
    return {
        "data": {
            "labels": sorted_months,
            "datasets": [
                {
                    "name": "Disbursements",
                    "values": [month_data[m] for m in sorted_months]
                }
            ]
        },
        "type": "line",
        "height": 300,
        "colors": ["#5fe65f"]
    }
