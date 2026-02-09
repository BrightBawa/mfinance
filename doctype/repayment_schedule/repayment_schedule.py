"""
Repayment Schedule DocType - Manages loan repayment schedule
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RepaymentSchedule(Document):
    def validate(self):
        """Calculate schedule totals"""
        self.calculate_totals()
    
    def calculate_totals(self):
        """Calculate total amounts from schedule entries"""
        total_principal = 0
        total_interest = 0
        total_amount = 0
        total_paid = 0
        total_outstanding = 0
        
        for entry in self.schedule_entries:
            total_principal += flt(entry.principal_amount)
            total_interest += flt(entry.interest_amount)
            total_amount += flt(entry.total_amount)
            total_paid += flt(entry.paid_amount)
            total_outstanding += flt(entry.outstanding_amount)
        
        self.total_principal = total_principal
        self.total_interest = total_interest
        self.total_amount = total_amount
        self.total_paid = total_paid
        self.total_outstanding = total_outstanding
        
        # Update status
        if total_outstanding <= 0 and total_paid > 0:
            self.status = "Completed"
        elif total_paid > 0:
            self.status = "Active"
