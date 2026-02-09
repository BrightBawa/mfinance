# Copyright (c) 2025, techypan@gmail.com and contributors
# For license information, please see license.txt

# import frappe
# bench restart
# bench clear-cache
# bench --site site2 reload-doc loan_management doctype loan_application



import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class LoanApplication(Document):
    def autoname(self):
        if self.full_name:
            series = make_autoname('.#####')  # Generate the series part
            self.name = f"{self.full_name}-Loan Application-{series}"
        else:
            frappe.throw("Full Name is required to generate a name.")
            
# def sort_array(source_array):
    
#     odd = []
#     for i in source_array:
#         if i % 2 == 1:
#             odd.append(i)
#     print(odd)
#     odd.sort()
#     idx = 0
#     for j in range(len(source_array)):
#         if source_array[j]% 2 == 1:
#             source_array[j] = odd[idx]
#             idx +=1 
#     print(source_array)
#     return source_array
# sort_array([5, 3, 2, 8, 1, 4, 11])
#loan_management.loan_management.loan_management.doctype.loan_application.loan_application.sort_array



