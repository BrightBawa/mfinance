"""
Loan Disbursement DocType - Handles loan disbursement and accounting
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class LoanDisbursement(Document):
    def validate(self):
        """Validate loan disbursement"""
        # Validate loan exists and is approved
        if self.loan:
            loan = frappe.get_doc("Loan", self.loan)
            
            # Check if loan is submitted
            if loan.docstatus != 1:
                frappe.throw(f"Loan {self.loan} must be submitted before disbursement")
            
            # Check if loan status allows disbursement
            if loan.status not in ["Approved", "Disbursed"]:
                frappe.throw(f"Loan {self.loan} status must be 'Approved' or 'Disbursed'. Current status: {loan.status}")
            
            # Fetch borrower and customer from loan
            if not self.borrower:
                self.borrower = loan.borrower
            if not self.customer:
                self.customer = loan.customer
            if not self.company:
                self.company = loan.company
            
            # Validate disbursed amount does not exceed approved amount
            if flt(self.disbursed_amount) > flt(loan.approved_amount):
                frappe.throw(f"Disbursed amount ({self.disbursed_amount}) cannot exceed approved loan amount ({loan.approved_amount})")
            
            # Check total disbursements
            total_disbursed = self.get_total_disbursed_amount(self.loan)
            if flt(total_disbursed) + flt(self.disbursed_amount) > flt(loan.approved_amount):
                frappe.throw(
                    f"Total disbursement ({flt(total_disbursed) + flt(self.disbursed_amount)}) "
                    f"would exceed approved loan amount ({loan.approved_amount})"
                )
    
    def before_submit(self):
        """Validate before submit"""
        if not self.disbursed_amount or flt(self.disbursed_amount) <= 0:
            frappe.throw("Disbursed amount must be greater than zero")
        
        if not self.bank_account:
            frappe.throw("Bank Account is required for disbursement")
        
        if not self.disbursement_date:
            frappe.throw("Disbursement Date is required")
    
    def on_submit(self):
        """Create GL entries and update loan status on submit"""
        # Create GL entries through Loan doctype
        loan = frappe.get_doc("Loan", self.loan)
        
        try:
            loan.make_disbursement_gl_entries(
                disbursement_amount=self.disbursed_amount,
                disbursement_date=self.disbursement_date,
                reference_no=self.name
            )
            
            # Mark GL entry as created
            self.db_set("gl_entry_created", 1)
            
            # Update loan status
            self.update_loan_status()
            
            # Set status to Disbursed
            self.db_set("status", "Disbursed")
            
            frappe.msgprint(f"Loan disbursement of {frappe.format_value(self.disbursed_amount, {'fieldtype': 'Currency'})} completed successfully")
            
        except Exception as e:
            frappe.throw(f"Failed to create GL entries: {str(e)}")
    
    def on_cancel(self):
        """Cancel GL entries and update loan status"""
        # Cancel GL entries
        from erpnext.accounts.general_ledger import make_reverse_gl_entries
        
        try:
            make_reverse_gl_entries(voucher_type="Loan Disbursement", voucher_no=self.name)
            
            # Update loan status
            self.update_loan_status()
            
            # Set status to Cancelled
            self.db_set("status", "Cancelled")
            
            frappe.msgprint("Loan disbursement cancelled and GL entries reversed")
            
        except Exception as e:
            frappe.throw(f"Failed to cancel GL entries: {str(e)}")
    
    def update_loan_status(self):
        """Update loan status based on disbursements"""
        loan = frappe.get_doc("Loan", self.loan)
        
        # Get total disbursed amount (excluding cancelled)
        total_disbursed = self.get_total_disbursed_amount(self.loan)
        
        if flt(total_disbursed) > 0:
            if flt(total_disbursed) >= flt(loan.approved_amount):
                # Fully disbursed
                loan.db_set("status", "Active")
                loan.db_set("disbursement_date", self.disbursement_date)
                loan.db_set("disbursed_amount", total_disbursed)
            else:
                # Partially disbursed
                loan.db_set("status", "Disbursed")
                loan.db_set("disbursed_amount", total_disbursed)
        else:
            # No disbursements or all cancelled
            loan.db_set("status", "Approved")
            loan.db_set("disbursed_amount", 0)
    
    def get_total_disbursed_amount(self, loan):
        """Get total disbursed amount for a loan (excluding cancelled)"""
        total = frappe.db.sql("""
            SELECT SUM(disbursed_amount) as total
            FROM `tabLoan Disbursement`
            WHERE loan = %s
            AND docstatus = 1
            AND name != %s
        """, (loan, self.name), as_dict=True)
        
        return flt(total[0].total) if total else 0
