"""
Loan Repayment DocType - Handles loan repayments, allocation and accounting
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate, add_days


class LoanRepayment(Document):
    def validate(self):
        """Validate loan repayment"""
        # Validate loan exists and is active
        if self.loan:
            loan = frappe.get_doc("Loan", self.loan)
            
            # Check if loan is submitted
            if loan.docstatus != 1:
                frappe.throw(f"Loan {self.loan} must be submitted before repayment")
            
            # Check if loan status allows repayment
            if loan.status not in ["Active", "Disbursed"]:
                frappe.throw(f"Loan {self.loan} status must be 'Active' or 'Disbursed' to accept repayments. Current status: {loan.status}")
            
            # Fetch borrower and customer from loan
            if not self.borrower:
                self.borrower = loan.borrower
            if not self.customer:
                self.customer = loan.customer
            if not self.company:
                self.company = loan.company
        
        # Calculate allocation totals
        self.calculate_allocation_totals()
        
        # Validate allocation does not exceed payment amount
        if flt(self.total_allocated) > flt(self.total_payment_amount):
            frappe.throw(f"Total allocated amount ({self.total_allocated}) cannot exceed total payment amount ({self.total_payment_amount})")
    
    def before_submit(self):
        """Validate before submit"""
        if not self.total_payment_amount or flt(self.total_payment_amount) <= 0:
            frappe.throw("Payment amount must be greater than zero")
        
        if not self.bank_account:
            frappe.throw("Bank Account is required for repayment")
        
        if not self.payment_date:
            frappe.throw("Payment Date is required")
        
        # Ensure payment is allocated
        if not self.allocations or len(self.allocations) == 0:
            frappe.throw("Please allocate the payment to repayment schedule entries")
        
        if flt(self.unallocated_amount) > 0:
            frappe.msgprint(f"Warning: Unallocated amount of {frappe.format_value(self.unallocated_amount, {'fieldtype': 'Currency'})} will not be applied", 
                          indicator="orange", alert=True)
    
    def on_submit(self):
        """Create GL entries and update repayment schedule on submit"""
        # Update repayment schedule
        self.update_repayment_schedule()
        
        # Create GL entries through Loan doctype
        loan = frappe.get_doc("Loan", self.loan)
        
        try:
            loan.make_repayment_gl_entries(
                principal_amount=self.principal_amount,
                interest_amount=self.interest_amount,
                penalty_amount=self.penalty_amount,
                payment_date=self.payment_date,
                reference_no=self.name
            )
            
            # Mark GL entry as created
            self.db_set("gl_entry_created", 1)
            
            # Update loan outstanding
            self.update_loan_outstanding()
            
            # Set status to Paid
            self.db_set("status", "Paid")
            
            frappe.msgprint(f"Loan repayment of {frappe.format_value(self.total_payment_amount, {'fieldtype': 'Currency'})} completed successfully")
            
        except Exception as e:
            frappe.throw(f"Failed to create GL entries: {str(e)}")
    
    def on_cancel(self):
        """Cancel GL entries and revert repayment schedule updates"""
        # Revert repayment schedule updates
        self.revert_repayment_schedule()
        
        # Cancel GL entries
        from erpnext.accounts.general_ledger import make_reverse_gl_entries
        
        try:
            make_reverse_gl_entries(voucher_type="Loan Repayment", voucher_no=self.name)
            
            # Update loan outstanding
            self.update_loan_outstanding()
            
            # Set status to Cancelled
            self.db_set("status", "Cancelled")
            
            frappe.msgprint("Loan repayment cancelled and GL entries reversed")
            
        except Exception as e:
            frappe.throw(f"Failed to cancel GL entries: {str(e)}")
    
    def calculate_allocation_totals(self):
        """Calculate totals from allocation table"""
        total_principal = 0
        total_interest = 0
        total_penalty = 0
        total_allocated = 0
        
        for allocation in self.allocations:
            # Calculate row total
            row_total = flt(allocation.allocated_principal) + flt(allocation.allocated_interest) + flt(allocation.allocated_penalty)
            allocation.total_allocated = row_total
            
            # Add to totals
            total_principal += flt(allocation.allocated_principal)
            total_interest += flt(allocation.allocated_interest)
            total_penalty += flt(allocation.allocated_penalty)
            total_allocated += row_total
        
        # Update header fields
        self.principal_amount = total_principal
        self.interest_amount = total_interest
        self.penalty_amount = total_penalty
        self.total_allocated = total_allocated
        self.unallocated_amount = flt(self.total_payment_amount) - flt(total_allocated)
    
    def update_repayment_schedule(self):
        """Update repayment schedule detail entries with payment"""
        for allocation in self.allocations:
            if not allocation.schedule_detail:
                continue
            
            # Get schedule detail
            schedule_detail = frappe.get_doc("Repayment Schedule Detail", allocation.schedule_detail)
            
            # Calculate new paid amount
            new_paid_amount = flt(schedule_detail.paid_amount) + flt(allocation.total_allocated)
            new_outstanding = flt(schedule_detail.total_amount) - new_paid_amount
            
            # Update status based on payment
            if new_outstanding <= 0:
                status = "Paid"
            elif new_paid_amount > 0:
                status = "Partially Paid"
            else:
                status = schedule_detail.status
            
            # Calculate days overdue
            days_overdue = 0
            if status != "Paid" and getdate(schedule_detail.due_date) < getdate(nowdate()):
                days_overdue = (getdate(nowdate()) - getdate(schedule_detail.due_date)).days
                if days_overdue > 0:
                    status = "Overdue"
            
            # Update schedule detail
            schedule_detail.db_set("paid_amount", new_paid_amount)
            schedule_detail.db_set("outstanding_amount", new_outstanding)
            schedule_detail.db_set("payment_date", self.payment_date)
            schedule_detail.db_set("status", status)
            schedule_detail.db_set("days_overdue", days_overdue)
            schedule_detail.db_set("payment_reference", self.name)
    
    def revert_repayment_schedule(self):
        """Revert repayment schedule updates on cancellation"""
        for allocation in self.allocations:
            if not allocation.schedule_detail:
                continue
            
            # Get schedule detail
            schedule_detail = frappe.get_doc("Repayment Schedule Detail", allocation.schedule_detail)
            
            # Calculate reverted amounts
            new_paid_amount = flt(schedule_detail.paid_amount) - flt(allocation.total_allocated)
            new_outstanding = flt(schedule_detail.total_amount) - new_paid_amount
            
            # Update status
            if new_paid_amount <= 0:
                status = "Pending"
                payment_date = None
                payment_reference = None
            elif new_outstanding <= 0:
                status = "Paid"
                payment_date = schedule_detail.payment_date
                payment_reference = schedule_detail.payment_reference
            else:
                status = "Partially Paid"
                payment_date = schedule_detail.payment_date
                payment_reference = schedule_detail.payment_reference
            
            # Calculate days overdue
            days_overdue = 0
            if status != "Paid" and getdate(schedule_detail.due_date) < getdate(nowdate()):
                days_overdue = (getdate(nowdate()) - getdate(schedule_detail.due_date)).days
                if days_overdue > 0:
                    status = "Overdue"
            
            # Update schedule detail
            schedule_detail.db_set("paid_amount", new_paid_amount)
            schedule_detail.db_set("outstanding_amount", new_outstanding)
            schedule_detail.db_set("payment_date", payment_date)
            schedule_detail.db_set("status", status)
            schedule_detail.db_set("days_overdue", days_overdue)
            schedule_detail.db_set("payment_reference", payment_reference)
    
    def update_loan_outstanding(self):
        """Update loan outstanding amount"""
        loan = frappe.get_doc("Loan", self.loan)
        
        # Calculate total outstanding from schedule
        total_outstanding = frappe.db.sql("""
            SELECT SUM(outstanding_amount) as total
            FROM `tabRepayment Schedule Detail`
            WHERE parent IN (
                SELECT name FROM `tabRepayment Schedule`
                WHERE loan = %s
            )
        """, self.loan, as_dict=True)
        
        outstanding = flt(total_outstanding[0].total) if total_outstanding else 0
        
        # Update loan
        loan.db_set("outstanding_amount", outstanding)
        
        # Update status if fully paid
        if outstanding <= 0:
            loan.db_set("status", "Closed")
            loan.db_set("closure_date", self.payment_date)


@frappe.whitelist()
def get_pending_schedule_entries(loan):
    """Get pending repayment schedule entries for a loan"""
    schedule = frappe.db.get_value("Repayment Schedule", {"loan": loan}, "name")
    
    if not schedule:
        return []
    
    entries = frappe.get_all(
        "Repayment Schedule Detail",
        filters={
            "parent": schedule,
            "status": ["in", ["Pending", "Partially Paid", "Overdue"]]
        },
        fields=["name", "due_date", "principal_amount", "interest_amount", 
                "penalty_amount", "total_amount", "paid_amount", "outstanding_amount", "status"],
        order_by="due_date asc"
    )
    
    return entries
