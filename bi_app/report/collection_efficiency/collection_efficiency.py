"""
Collection Efficiency Report - Measures collection performance vs due amounts
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
            "fieldname": "period",
            "label": _("Period"),
            "fieldtype": "Data",
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
            "fieldname": "due_amount",
            "label": _("Amount Due"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "collected_amount",
            "label": _("Amount Collected"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "collection_rate",
            "label": _("Collection Rate %"),
            "fieldtype": "Percent",
            "width": 130
        },
        {
            "fieldname": "overdue_amount",
            "label": _("Overdue Amount"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "number_of_payments",
            "label": _("Payments"),
            "fieldtype": "Int",
            "width": 100
        }
    ]


def get_data(filters):
    """Get collection efficiency data"""
    from_date = filters.get("from_date") or add_months(nowdate(), -1)
    to_date = filters.get("to_date") or nowdate()
    
    conditions = get_conditions(filters)
    
    # Get due amounts
    due_data = frappe.db.sql(f"""
        SELECT
            COALESCE(l.branch, 'No Branch') as branch,
            SUM(rsd.total_amount) as due_amount,
            SUM(CASE WHEN rsd.status = 'Overdue' THEN rsd.outstanding_amount ELSE 0 END) as overdue_amount
        FROM
            `tabRepayment Schedule` rs
        JOIN
            `tabRepayment Schedule Detail` rsd ON rsd.parent = rs.name
        JOIN
            `tabLoan` l ON l.name = rs.loan
        WHERE
            rsd.due_date BETWEEN %(from_date)s AND %(to_date)s
            AND l.docstatus = 1
            {conditions}
        GROUP BY
            l.branch
    """, {"from_date": from_date, "to_date": to_date, **filters}, as_dict=1)
    
    # Get collected amounts
    collected_data = frappe.db.sql(f"""
        SELECT
            COALESCE(l.branch, 'No Branch') as branch,
            SUM(lr.total_payment_amount) as collected_amount,
            COUNT(lr.name) as number_of_payments
        FROM
            `tabLoan Repayment` lr
        JOIN
            `tabLoan` l ON l.name = lr.loan
        WHERE
            lr.payment_date BETWEEN %(from_date)s AND %(to_date)s
            AND lr.docstatus = 1
            {conditions}
        GROUP BY
            l.branch
    """, {"from_date": from_date, "to_date": to_date, **filters}, as_dict=1)
    
    # Combine data
    branch_data = {}
    
    for row in due_data:
        branch = row.get("branch")
        branch_data[branch] = {
            "period": f"{from_date} to {to_date}",
            "branch": branch,
            "due_amount": flt(row.get("due_amount")),
            "overdue_amount": flt(row.get("overdue_amount")),
            "collected_amount": 0,
            "number_of_payments": 0
        }
    
    for row in collected_data:
        branch = row.get("branch")
        if branch not in branch_data:
            branch_data[branch] = {
                "period": f"{from_date} to {to_date}",
                "branch": branch,
                "due_amount": 0,
                "overdue_amount": 0,
                "collected_amount": 0,
                "number_of_payments": 0
            }
        
        branch_data[branch]["collected_amount"] = flt(row.get("collected_amount"))
        branch_data[branch]["number_of_payments"] = row.get("number_of_payments")
    
    # Calculate collection rate
    data = []
    for branch, values in branch_data.items():
        if values["due_amount"] > 0:
            values["collection_rate"] = (values["collected_amount"] / values["due_amount"]) * 100
        else:
            values["collection_rate"] = 0
        
        data.append(values)
    
    return data


def get_conditions(filters):
    """Build filter conditions"""
    conditions = []
    
    if filters.get("company"):
        conditions.append("AND l.company = %(company)s")
    
    if filters.get("branch"):
        conditions.append("AND l.branch = %(branch)s")
    
    return " ".join(conditions)


def get_summary(data):
    """Calculate summary statistics"""
    total_due = sum(flt(row.get("due_amount")) for row in data)
    total_collected = sum(flt(row.get("collected_amount")) for row in data)
    total_overdue = sum(flt(row.get("overdue_amount")) for row in data)
    
    collection_rate = (total_collected / total_due * 100) if total_due > 0 else 0
    
    return [
        {
            "value": total_due,
            "indicator": "Blue",
            "label": _("Total Due"),
            "datatype": "Currency"
        },
        {
            "value": total_collected,
            "indicator": "Green",
            "label": _("Total Collected"),
            "datatype": "Currency"
        },
        {
            "value": collection_rate,
            "indicator": "Green" if collection_rate >= 90 else "Orange",
            "label": _("Collection Rate"),
            "datatype": "Percent"
        },
        {
            "value": total_overdue,
            "indicator": "Red",
            "label": _("Total Overdue"),
            "datatype": "Currency"
        }
    ]


def get_chart_data(data):
    """Generate chart data"""
    return {
        "data": {
            "labels": [row.get("branch") for row in data],
            "datasets": [
                {
                    "name": "Collection Rate %",
                    "values": [row.get("collection_rate") for row in data]
                }
            ]
        },
        "type": "bar",
        "height": 300,
        "colors": ["#5fe65f"]
    }
