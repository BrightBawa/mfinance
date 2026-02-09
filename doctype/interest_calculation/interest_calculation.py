# Copyright (c) 2025, techypan@gmail.com and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class InterestCalculation(Document):
	pass

	@frappe.whitelist()
	def calculate_interest(doc):
		doc = json.loads(doc)
		frappe.msgprint(f"document:{doc}")
    # Extract values from the document
		approved_amount = doc.get("approved_amount", 0)
		rate = doc.get("interest", 0) / 100  # Convert percentage to a decimal
		tenure = doc.get("tenure", 0)  # Time in years

		
		interest_amount = approved_amount * rate * tenure
		final_amount = approved_amount + interest_amount

		# Add interest amount back to the document for reference
		doc["interest_amount"] = interest_amount
		doc["final_amount"] = final_amount
		frappe.msgprint(f"Interest calculated successfully.final amount is {final_amount} and  interest amount is {interest_amount}")
		return {
			 "interest_amount": interest_amount,
        	"final_amount": final_amount,
		} 
	
		