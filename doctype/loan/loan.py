"""
Loan DocType methods and validations for bi_app
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate
from datetime import datetime
from bi_app.microfinance.loan_utils import (
    calculate_repayment_schedule,
    verify_government_worker_affordability,
)


class Loan(Document):
    def validate(self):
        """Validate loan on save"""
        # Branch is mandatory
        if not self.branch:
            frappe.throw("Branch is mandatory")
        
        # Populate customer from borrower
        if self.borrower and not self.customer:
            borrower = frappe.get_doc("Borrower", self.borrower)
            if borrower.customer:
                self.customer = borrower.customer
            else:
                frappe.throw(f"Borrower {self.borrower} does not have a linked Customer. Please create one first.")
        
        # Validate interest rate is within product range
        if self.loan_product:
            product = frappe.get_doc("Loan Product", self.loan_product)
            if self.interest_rate < product.annual_interest_rate_min or self.interest_rate > product.annual_interest_rate_max:
                frappe.throw(
                    f"Interest rate must be between {product.annual_interest_rate_min} and {product.annual_interest_rate_max}"
                )
        
        # Validate tenure is within product range
        if self.tenure_months:
            if self.tenure_months < (self.loan_product_doc.min_tenure_months if self.loan_product_doc else 3):
                frappe.throw("Tenure is below minimum")
    
    def before_submit(self):
        """Validate before submitting loan document"""
        # Validate company is set
        if not self.company:
            frappe.throw("Company is required before submitting the loan")
        
        # Validate customer linkage
        if not self.customer:
            frappe.throw("Customer must be linked to the borrower before submission")
        
        # Validate approved amount is set
        if not self.approved_amount or self.approved_amount <= 0:
            frappe.throw("Approved amount must be greater than zero")
        
        # Validate accounting accounts are configured
        if not self.loan_receivable_account:
            frappe.throw("Loan Receivable Account is required")
        
        if not self.interest_income_account:
            frappe.throw("Interest Income Account is required")
        
        if not self.interest_receivable_account:
            frappe.throw("Interest Receivable Account is required")
        
        if not self.company_bank_account:
            frappe.throw("Company Bank Account is required")
        
        # Validate tenure and interest rate
        if not self.tenure_months or self.tenure_months <= 0:
            frappe.throw("Tenure (in months) must be greater than zero")
        
        if not self.interest_rate or self.interest_rate < 0:
            frappe.throw("Interest rate must be specified")
    
    def on_submit(self):
        """Actions when loan is submitted"""
        if self.government_verification_required:
            self.verify_government_worker()
        
        # Generate repayment schedule
        self.generate_repayment_schedule()
    
    def verify_government_worker(self):
        """Verify government worker affordability"""
        if not self.government_verification_required:
            return
        
        borrower = frappe.get_doc("Borrower", self.borrower)
        if borrower.employment_type != "Government":
            frappe.throw("Government verification required but borrower is not a government employee")
        
        # Get GOGTPRS settings from app config
        settings = frappe.get_doc("Bestinvest Settings") if frappe.db.exists("Bestinvest Settings") else None
        
        if not settings or not settings.gogtprs_api_endpoint:
            # Skip verification if not configured, but flag for manual review
            self.government_verification_status = "Manual Review"
            self.government_verification_flag_date = datetime.now()
            self.government_verification_notes = "GOGTPRS API not configured - manual verification required"
            return
        
        result = verify_government_worker_affordability(
            borrower.government_id_number,
            settings.gogtprs_api_endpoint,
            settings.gogtprs_api_key,
            self.name,
        )
        
        if result:
            self.government_verification_status = "Verified"
            self.government_verification_notes = f"Monthly Income: {result.get('monthly_income')}, Recommended Max Loan: {result.get('recommended_max_loan')}"
    
    def generate_repayment_schedule(self):
        """Generate repayment schedule for the loan"""
        schedule_data = calculate_repayment_schedule(
            self.approved_amount or self.requested_amount,
            self.tenure_months,
            self.interest_rate,
            self.interest_calculation_method,
            self.repayment_frequency,
        )
        
        # Create Repayment Schedule document
        repayment_schedule = frappe.new_doc("Repayment Schedule")
        repayment_schedule.loan = self.name
        repayment_schedule.currency = self.currency
        repayment_schedule.total_principal = schedule_data["total_principal"]
        repayment_schedule.total_interest = schedule_data["total_interest"]
        repayment_schedule.total_amount = schedule_data["total_amount"]
        
        for entry in schedule_data["schedule_entries"]:
            repayment_schedule.append("schedule_entries", entry)
        
        repayment_schedule.insert()
    
    def make_disbursement_gl_entries(self, disbursement_amount, disbursement_date, reference_no=None):
        """
        Create GL Entries for loan disbursement
        
        Args:
            disbursement_amount (float): Amount being disbursed
            disbursement_date (date): Date of disbursement
            reference_no (str): Reference number for the disbursement
        
        GL Entries:
            DR Loan Receivable Account
            CR Company Bank Account
        """
        from erpnext.accounts.general_ledger import make_gl_entries
        
        gl_entries = []
        
        # Debit Loan Receivable Account (Asset increases)
        gl_entries.append(
            self.get_gl_dict({
                "account": self.loan_receivable_account,
                "party_type": "Customer",
                "party": self.customer,
                "debit": flt(disbursement_amount),
                "debit_in_account_currency": flt(disbursement_amount),
                "against": self.company_bank_account,
                "cost_center": self.get_default_cost_center(),
                "posting_date": getdate(disbursement_date),
                "remarks": f"Loan disbursement for {self.name}",
                "voucher_type": "Loan",
                "voucher_no": self.name,
                "against_voucher_type": "Loan",
                "against_voucher": self.name
            })
        )
        
        # Credit Company Bank Account (Asset decreases)
        gl_entries.append(
            self.get_gl_dict({
                "account": self.company_bank_account,
                "credit": flt(disbursement_amount),
                "credit_in_account_currency": flt(disbursement_amount),
                "against": self.loan_receivable_account,
                "cost_center": self.get_default_cost_center(),
                "posting_date": getdate(disbursement_date),
                "remarks": f"Loan disbursement for {self.name}",
                "voucher_type": "Loan",
                "voucher_no": self.name
            })
        )
        
        if gl_entries:
            make_gl_entries(gl_entries, cancel=False, adv_adj=False)
            frappe.msgprint(f"GL Entries created for loan disbursement of {frappe.format_value(disbursement_amount, {'fieldtype': 'Currency'})}")
    
    def make_repayment_gl_entries(self, principal_amount, interest_amount, penalty_amount=0, 
                                    payment_date=None, reference_no=None):
        """
        Create GL Entries for loan repayment
        
        Args:
            principal_amount (float): Principal portion of the repayment
            interest_amount (float): Interest portion of the repayment
            penalty_amount (float): Penalty portion of the repayment (optional)
            payment_date (date): Date of payment
            reference_no (str): Reference number for the payment
        
        GL Entries:
            DR Company Bank Account
            CR Loan Receivable Account (principal)
            CR Interest Income Account (interest)
            CR Interest Income Account or Penalty Income Account (penalty)
        """
        from erpnext.accounts.general_ledger import make_gl_entries
        
        if not payment_date:
            payment_date = nowdate()
        
        gl_entries = []
        total_amount = flt(principal_amount) + flt(interest_amount) + flt(penalty_amount)
        
        # Debit Company Bank Account (Asset increases)
        gl_entries.append(
            self.get_gl_dict({
                "account": self.company_bank_account,
                "debit": flt(total_amount),
                "debit_in_account_currency": flt(total_amount),
                "against": f"{self.loan_receivable_account}, {self.interest_income_account}",
                "cost_center": self.get_default_cost_center(),
                "posting_date": getdate(payment_date),
                "remarks": f"Loan repayment for {self.name}",
                "voucher_type": "Loan Repayment",
                "voucher_no": reference_no or self.name
            })
        )
        
        # Credit Loan Receivable Account for principal (Asset decreases)
        if flt(principal_amount) > 0:
            gl_entries.append(
                self.get_gl_dict({
                    "account": self.loan_receivable_account,
                    "party_type": "Customer",
                    "party": self.customer,
                    "credit": flt(principal_amount),
                    "credit_in_account_currency": flt(principal_amount),
                    "against": self.company_bank_account,
                    "cost_center": self.get_default_cost_center(),
                    "posting_date": getdate(payment_date),
                    "remarks": f"Principal repayment for {self.name}",
                    "voucher_type": "Loan Repayment",
                    "voucher_no": reference_no or self.name,
                    "against_voucher_type": "Loan",
                    "against_voucher": self.name
                })
            )
        
        # Credit Interest Income Account (Income increases)
        if flt(interest_amount) > 0:
            gl_entries.append(
                self.get_gl_dict({
                    "account": self.interest_income_account,
                    "credit": flt(interest_amount),
                    "credit_in_account_currency": flt(interest_amount),
                    "against": self.company_bank_account,
                    "cost_center": self.get_default_cost_center(),
                    "posting_date": getdate(payment_date),
                    "remarks": f"Interest income for {self.name}",
                    "voucher_type": "Loan Repayment",
                    "voucher_no": reference_no or self.name
                })
            )
        
        # Credit Interest Income Account for penalty (or separate penalty account if configured)
        if flt(penalty_amount) > 0:
            gl_entries.append(
                self.get_gl_dict({
                    "account": self.interest_income_account,  # Could use separate penalty account
                    "credit": flt(penalty_amount),
                    "credit_in_account_currency": flt(penalty_amount),
                    "against": self.company_bank_account,
                    "cost_center": self.get_default_cost_center(),
                    "posting_date": getdate(payment_date),
                    "remarks": f"Penalty income for {self.name}",
                    "voucher_type": "Loan Repayment",
                    "voucher_no": reference_no or self.name
                })
            )
        
        if gl_entries:
            make_gl_entries(gl_entries, cancel=False, adv_adj=False)
            frappe.msgprint(f"GL Entries created for loan repayment of {frappe.format_value(total_amount, {'fieldtype': 'Currency'})}")
    
    def get_gl_dict(self, args):
        """Build GL Entry dict with company and other defaults"""
        gl_dict = frappe._dict({
            "company": self.company,
            "voucher_type": args.get("voucher_type") or self.doctype,
            "voucher_no": args.get("voucher_no") or self.name,
            "posting_date": args.get("posting_date") or getdate(),
            "account": args.get("account"),
            "party_type": args.get("party_type"),
            "party": args.get("party"),
            "cost_center": args.get("cost_center"),
            "debit": flt(args.get("debit"), 2),
            "credit": flt(args.get("credit"), 2),
            "debit_in_account_currency": flt(args.get("debit_in_account_currency"), 2),
            "credit_in_account_currency": flt(args.get("credit_in_account_currency"), 2),
            "against": args.get("against"),
            "against_voucher_type": args.get("against_voucher_type"),
            "against_voucher": args.get("against_voucher"),
            "remarks": args.get("remarks"),
            "is_opening": args.get("is_opening") or "No"
        })
        
        return gl_dict
    
    def get_default_cost_center(self):
        """Get default cost center for the company"""
        cost_center = frappe.db.get_value("Company", self.company, "cost_center")
        if not cost_center:
            # Get first cost center for the company
            cost_center = frappe.db.get_value("Cost Center", 
                {"company": self.company, "is_group": 0}, 
                "name")
        return cost_center
    
    @property
    def loan_product_doc(self):
        """Get loan product document"""
        if self.loan_product:
            return frappe.get_doc("Loan Product", self.loan_product)
        return None
    
    def get_repayment_frequency(self):
        """Get repayment frequency (from override or product default)"""
        if self.repayment_frequency:
            return self.repayment_frequency
        elif self.loan_product_doc:
            return self.loan_product_doc.repayment_frequency
        return "Monthly"
