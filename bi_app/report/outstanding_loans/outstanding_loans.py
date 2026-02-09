"""
Outstanding Loans Report - Shows all active loans with outstanding balances
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


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
            "fieldname": "customer",
            "label": _("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
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
            "fieldname": "disbursed_amount",
            "label": _("Disbursed Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "total_repaid",
            "label": _("Total Repaid"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "outstanding_principal",
            "label": _("Outstanding Principal"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "outstanding_interest",
            "label": _("Outstanding Interest"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "total_outstanding",
            "label": _("Total Outstanding"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "disbursement_date",
            "label": _("Disbursement Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "maturity_date",
            "label": _("Maturity Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "days_outstanding",
            "label": _("Days Outstanding"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        }
    ]


def get_data(filters):
    """Get outstanding loans data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT
            l.name,
            l.borrower,
            l.customer,
            l.branch,
            l.disbursed_amount,
            COALESCE(
                (SELECT SUM(rsd.paid_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name), 0
            ) as total_repaid,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name
                 AND rsd.principal_amount > 0), 0
            ) as outstanding_principal,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name
                 AND rsd.interest_amount > 0), 0
            ) as outstanding_interest,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name), 0
            ) as total_outstanding,
            l.disbursement_date,
            DATE_ADD(l.disbursement_date, INTERVAL l.tenure_months MONTH) as maturity_date,
            DATEDIFF(CURDATE(), l.disbursement_date) as days_outstanding,
            l.status
        FROM
            `tabLoan` l
        WHERE
            l.docstatus = 1
            AND l.status IN ('Active', 'Disbursed')
            {conditions}
        HAVING
            total_outstanding > 0
        ORDER BY
            total_outstanding DESC
    """, filters, as_dict=1)
    
    return data


def get_conditions(filters):
    """Build filter conditions"""
    conditions = []
    
    if filters.get("company"):
        conditions.append("AND l.company = %(company)s")
    
    if filters.get("branch"):
        conditions.append("AND l.branch = %(branch)s")
    
    if filters.get("borrower"):
        conditions.append("AND l.borrower = %(borrower)s")
    
    if filters.get("loan_product"):
        conditions.append("AND l.loan_product = %(loan_product)s")
    
    if filters.get("from_date"):
        conditions.append("AND l.disbursement_date >= %(from_date)s")
    
    if filters.get("to_date"):
        conditions.append("AND l.disbursement_date <= %(to_date)s")
    
    return " ".join(conditions)
