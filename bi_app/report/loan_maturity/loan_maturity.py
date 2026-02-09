"""
Loan Maturity Report - Shows loans approaching or past maturity date
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_days, add_months


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    
    return columns, data, None, None, summary


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
            "fieldname": "maturity_date",
            "label": _("Maturity Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "days_to_maturity",
            "label": _("Days to Maturity"),
            "fieldtype": "Int",
            "width": 130
        },
        {
            "fieldname": "maturity_bucket",
            "label": _("Maturity Bucket"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "disbursed_amount",
            "label": _("Disbursed Amount"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "outstanding_amount",
            "label": _("Outstanding"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get loan maturity data"""
    conditions = get_conditions(filters)
    
    # Default: Show loans maturing in next 90 days or already matured
    maturity_days = filters.get("maturity_days") or 90
    
    data = frappe.db.sql(f"""
        SELECT
            l.name,
            l.borrower,
            l.branch,
            l.loan_product,
            l.disbursement_date,
            DATE_ADD(l.disbursement_date, INTERVAL l.tenure_months MONTH) as maturity_date,
            DATEDIFF(DATE_ADD(l.disbursement_date, INTERVAL l.tenure_months MONTH), CURDATE()) as days_to_maturity,
            l.disbursed_amount,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name), 0
            ) as outstanding_amount,
            l.status
        FROM
            `tabLoan` l
        WHERE
            l.docstatus = 1
            AND l.status IN ('Active', 'Disbursed')
            {conditions}
        HAVING
            days_to_maturity <= %(maturity_days)s
        ORDER BY
            days_to_maturity ASC
    """, {"maturity_days": maturity_days, **filters}, as_dict=1)
    
    # Add maturity bucket classification
    for row in data:
        days = row.get("days_to_maturity") or 0
        
        if days < 0:
            row["maturity_bucket"] = "Overdue"
        elif days <= 7:
            row["maturity_bucket"] = "0-7 Days"
        elif days <= 15:
            row["maturity_bucket"] = "8-15 Days"
        elif days <= 30:
            row["maturity_bucket"] = "16-30 Days"
        elif days <= 60:
            row["maturity_bucket"] = "31-60 Days"
        elif days <= 90:
            row["maturity_bucket"] = "61-90 Days"
        else:
            row["maturity_bucket"] = "90+ Days"
    
    return data


def get_conditions(filters):
    """Build filter conditions"""
    conditions = []
    
    if filters.get("company"):
        conditions.append("AND l.company = %(company)s")
    
    if filters.get("branch"):
        conditions.append("AND l.branch = %(branch)s")
    
    if filters.get("loan_product"):
        conditions.append("AND l.loan_product = %(loan_product)s")
    
    return " ".join(conditions)


def get_summary(data):
    """Calculate maturity summary"""
    total_loans = len(data)
    total_outstanding = sum(flt(row.get("outstanding_amount")) for row in data)
    
    overdue = sum(1 for row in data if row.get("days_to_maturity", 0) < 0)
    within_30_days = sum(1 for row in data if 0 <= row.get("days_to_maturity", 0) <= 30)
    
    return [
        {
            "value": total_loans,
            "indicator": "Blue",
            "label": _("Loans Maturing"),
            "datatype": "Int"
        },
        {
            "value": overdue,
            "indicator": "Red",
            "label": _("Overdue Maturity"),
            "datatype": "Int"
        },
        {
            "value": within_30_days,
            "indicator": "Orange",
            "label": _("Maturing in 30 Days"),
            "datatype": "Int"
        },
        {
            "value": total_outstanding,
            "indicator": "Blue",
            "label": _("Total Outstanding"),
            "datatype": "Currency"
        }
    ]
