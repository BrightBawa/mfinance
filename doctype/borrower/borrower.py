# Copyright (c) 2026, Bright Bawa and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class Borrower(Document):
	def validate(self):
		"""Validate borrower data before saving"""
		self.validate_age()
		self.validate_duplicate_government_id()
		
	def after_insert(self):
		"""Create ERPNext Customer after borrower is created"""
		if not self.customer:
			self.create_erpnext_customer()
	
	def validate_age(self):
		"""Ensure borrower meets minimum age requirement"""
		if self.date_of_birth:
			age = (getdate(today()) - getdate(self.date_of_birth)).days / 365.25
			if age < 18:
				frappe.throw("Borrower must be at least 18 years old")
			if age > 100:
				frappe.throw("Please verify the date of birth")
	
	def validate_duplicate_government_id(self):
		"""Check for duplicate government ID numbers"""
		if self.government_id_number:
			existing = frappe.db.exists("Borrower", {
				"government_id_number": self.government_id_number,
				"name": ["!=", self.name]
			})
			if existing:
				frappe.throw(f"A borrower with Government ID {self.government_id_number} already exists")
	
	def create_erpnext_customer(self):
		"""Automatically create ERPNext Customer record for accounting integration"""
		try:
			# Check if customer already exists with this email
			existing_customer = frappe.db.get_value("Customer", {"email_id": self.email})
			
			if existing_customer:
				self.db_set("customer", existing_customer, update_modified=False)
				frappe.msgprint(f"Linked to existing Customer: {existing_customer}")
				return existing_customer
			
			# Create new customer
			customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": self.full_name,
				"customer_type": "Individual",
				"customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual",
				"territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
				"email_id": self.email,
				"mobile_no": self.mobile_number,
				"customer_primary_contact": self.full_name,
				"custom_borrower_id": self.name
			})
			
			customer.flags.ignore_mandatory = True
			customer.insert(ignore_permissions=True)
			
			# Link customer back to borrower
			self.db_set("customer", customer.name, update_modified=False)
			
			frappe.msgprint(f"Created ERPNext Customer: {customer.name}", alert=True)
			
			return customer.name
			
		except Exception as e:
			frappe.log_error(f"Failed to create customer for borrower {self.name}: {str(e)}")
			frappe.msgprint(f"Warning: Could not create ERPNext Customer. Error: {str(e)}", indicator="orange")


@frappe.whitelist()
def get_borrower_outstanding_loans(borrower):
	"""Get total outstanding amount for a borrower across all active loans"""
	outstanding = frappe.db.sql("""
		SELECT 
			COUNT(*) as loan_count,
			SUM(approved_amount - COALESCE(
				(SELECT SUM(paid_amount) 
				 FROM `tabRepayment Schedule Detail` rsd
				 JOIN `tabRepayment Schedule` rs ON rsd.parent = rs.name
				 WHERE rs.loan = l.name), 0
			)) as total_outstanding
		FROM `tabLoan` l
		WHERE l.borrower = %s
		AND l.docstatus = 1
		AND l.status IN ('Active', 'Disbursed')
	""", borrower, as_dict=True)
	
	return outstanding[0] if outstanding else {"loan_count": 0, "total_outstanding": 0}


@frappe.whitelist()
def calculate_credit_score(borrower):
	"""Simple credit score calculation based on payment history and verification status"""
	borrower_doc = frappe.get_doc("Borrower", borrower)
	
	score = 500  # Base score
	
	# Add points for verification
	if borrower_doc.verified:
		score += 100
	if borrower_doc.id_verification_status == "Verified":
		score += 50
	if borrower_doc.income_verification_status == "Verified":
		score += 50
	
	# Check payment history
	loans = frappe.get_all("Loan", 
		filters={"borrower": borrower, "docstatus": 1},
		fields=["name"])
	
	if loans:
		# Get overdue payments
		overdue_count = frappe.db.count("Repayment Schedule Detail", {
			"parenttype": "Repayment Schedule",
			"status": "Overdue"
		})
		
		# Penalize for overdue payments
		score -= (overdue_count * 20)
		
		# Bonus for completed loans
		completed_loans = frappe.db.count("Loan", {
			"borrower": borrower,
			"status": "Closed",
			"docstatus": 1
		})
		score += (completed_loans * 50)
	
	# Cap between 300 and 850
	score = max(300, min(850, score))
	
	return score
