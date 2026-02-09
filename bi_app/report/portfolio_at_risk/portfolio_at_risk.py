"""
Portfolio at Risk (PAR) Report - Shows loans with overdue payments by aging buckets
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


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
            "fieldname": "outstanding_amount",
            "label": _("Outstanding Amount"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "overdue_amount",
            "label": _("Overdue Amount"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "days_overdue",
            "label": _("Days Overdue"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "par_bucket",
            "label": _("PAR Bucket"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "last_payment_date",
            "label": _("Last Payment"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "disbursement_date",
            "label": _("Disbursed On"),
            "fieldtype": "Date",
            "width": 120
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
    """Get PAR data"""
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT
            l.name,
            l.borrower,
            l.branch,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name), 0
            ) as outstanding_amount,
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name
                 AND rsd.status = 'Overdue'), 0
            ) as overdue_amount,
            COALESCE(
                (SELECT MAX(rsd.days_overdue)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name
                 AND rsd.status = 'Overdue'), 0
            ) as days_overdue,
            COALESCE(
                (SELECT MAX(lr.payment_date)
                 FROM `tabLoan Repayment` lr
                 WHERE lr.loan = l.name
                 AND lr.docstatus = 1), NULL
            ) as last_payment_date,
            l.disbursement_date,
            l.owner as loan_officer
        FROM
            `tabLoan` l
        WHERE
            l.docstatus = 1
            AND l.status IN ('Active', 'Disbursed')
            {conditions}
        HAVING
            overdue_amount > 0
        ORDER BY
            days_overdue DESC, overdue_amount DESC
    """, filters, as_dict=1)
    
    # Add PAR bucket classification
    for row in data:
        days = row.get("days_overdue") or 0
        
        if days >= 1 and days <= 30:
            row["par_bucket"] = "PAR 1-30"
        elif days >= 31 and days <= 60:
            row["par_bucket"] = "PAR 31-60"
        elif days >= 61 and days <= 90:
            row["par_bucket"] = "PAR 61-90"
        elif days >= 91 and days <= 180:
            row["par_bucket"] = "PAR 91-180"
        elif days > 180:
            row["par_bucket"] = "PAR 180+"
        else:
            row["par_bucket"] = "Current"
    
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
    """Calculate PAR summary statistics"""
    total_outstanding = sum(flt(row.get("outstanding_amount")) for row in data)
    total_overdue = sum(flt(row.get("overdue_amount")) for row in data)
    
    # Calculate total portfolio (all active loans)
    total_portfolio = frappe.db.sql("""
        SELECT SUM(
            COALESCE(
                (SELECT SUM(rsd.outstanding_amount)
                 FROM `tabRepayment Schedule` rs
                 JOIN `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
                 WHERE rs.loan = l.name), 0
            )
        ) as total
        FROM `tabLoan` l
        WHERE l.docstatus = 1
        AND l.status IN ('Active', 'Disbursed')
    """, as_dict=1)
    
    portfolio_value = flt(total_portfolio[0].get("total")) if total_portfolio else 0
    par_ratio = (total_overdue / portfolio_value * 100) if portfolio_value > 0 else 0
    
    # Count loans by bucket
    par_buckets = {}
    for row in data:
        bucket = row.get("par_bucket")
        par_buckets[bucket] = par_buckets.get(bucket, 0) + 1
    
    return [
        {
            "value": portfolio_value,
            "indicator": "Blue",
            "label": _("Total Portfolio"),
            "datatype": "Currency"
        },
        {
            "value": total_overdue,
            "indicator": "Red",
            "label": _("Total at Risk"),
            "datatype": "Currency"
        },
        {
            "value": par_ratio,
            "indicator": "Red" if par_ratio > 5 else "Orange" if par_ratio > 2 else "Green",
            "label": _("PAR Ratio"),
            "datatype": "Percent"
        },
        {
            "value": len(data),
            "indicator": "Orange",
            "label": _("Loans at Risk"),
            "datatype": "Int"
        }
    ]


def get_chart_data(data):
    """Generate PAR bucket distribution chart"""
    bucket_data = {}
    
    for row in data:
        bucket = row.get("par_bucket")
        bucket_data[bucket] = bucket_data.get(bucket, 0) + flt(row.get("overdue_amount"))
    
    # Sort buckets
    bucket_order = ["PAR 1-30", "PAR 31-60", "PAR 61-90", "PAR 91-180", "PAR 180+"]
    labels = [b for b in bucket_order if b in bucket_data]
    values = [bucket_data[b] for b in labels]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Overdue Amount",
                    "values": values
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#ff6c5f"]
    }
