# Copyright (c) 2025, techypan@gmail.com and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document


# class LoanApproval(Document):
# 	def autoname(self):
# 		if self.full_name:
#     		self.name = f"Application-{self.full_name}-{frappe.generate_autoname('.#####')}"
#    		else:
#     		frappe.throw("Full Name is required to generate a name.")

import frappe
from frappe.model.document import Document


class LoanApproval(Document):
    def autoname(self):
        if self.full_name:
            self.name = f"Application-{self.full_name}-{frappe.generate_autoname('.#####')}"
        else:
            frappe.throw("Full Name is required to generate a name.")
