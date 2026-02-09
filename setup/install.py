"""
Installation and setup functions for bi_app
Creates necessary Chart of Accounts for microfinance operations
"""

import frappe
from frappe import _


def after_install():
    """Hook called after app installation"""
    frappe.msgprint(_("Setting up BI App microfinance accounts..."), alert=True)
    
    # Create accounts for all companies
    companies = frappe.get_all("Company", fields=["name", "default_currency"])
    
    for company in companies:
        try:
            create_microfinance_accounts(company.name, company.default_currency)
            frappe.msgprint(_(f"Microfinance accounts created for {company.name}"), alert=True)
        except Exception as e:
            frappe.log_error(f"Error creating accounts for {company.name}: {str(e)}")
            frappe.msgprint(_(f"Error creating accounts for {company.name}. Check Error Log."), 
                          indicator="red", alert=True)
    
    frappe.db.commit()


def create_microfinance_accounts(company, currency="BWP"):
    """
    Create microfinance-specific accounts in the Chart of Accounts
    
    Args:
        company (str): Company name
        currency (str): Company currency (default: BWP)
    """
    
    # Get root accounts
    root_assets = frappe.db.get_value("Account", 
        {"company": company, "account_type": "Asset", "is_group": 1, "parent_account": ""}, 
        "name")
    
    root_income = frappe.db.get_value("Account", 
        {"company": company, "root_type": "Income", "is_group": 1, "parent_account": ""}, 
        "name")
    
    if not root_assets or not root_income:
        frappe.throw(_("Root Asset or Income account not found. Please ensure Chart of Accounts is set up."))
    
    # Define microfinance accounts structure
    accounts = [
        # Asset Accounts
        {
            "account_name": "Loans and Advances",
            "parent_account": root_assets,
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        },
        {
            "account_name": "Loan Receivable - Microfinance",
            "parent_account": f"Loans and Advances - {company}",
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        },
        {
            "account_name": "Interest Receivable - Microfinance",
            "parent_account": f"Loans and Advances - {company}",
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        },
        {
            "account_name": "Penalty Receivable - Microfinance",
            "parent_account": f"Loans and Advances - {company}",
            "is_group": 0,
            "account_type": "Receivable",
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        },
        
        # Income Accounts
        {
            "account_name": "Microfinance Income",
            "parent_account": root_income,
            "is_group": 1,
            "root_type": "Income",
            "report_type": "Profit and Loss"
        },
        {
            "account_name": "Interest Income - Loans",
            "parent_account": f"Microfinance Income - {company}",
            "is_group": 0,
            "account_type": "Income Account",
            "root_type": "Income",
            "report_type": "Profit and Loss"
        },
        {
            "account_name": "Penalty Income - Loans",
            "parent_account": f"Microfinance Income - {company}",
            "is_group": 0,
            "account_type": "Income Account",
            "root_type": "Income",
            "report_type": "Profit and Loss"
        },
        {
            "account_name": "Processing Fee Income",
            "parent_account": f"Microfinance Income - {company}",
            "is_group": 0,
            "account_type": "Income Account",
            "root_type": "Income",
            "report_type": "Profit and Loss"
        }
    ]
    
    # Create accounts
    for account in accounts:
        account_name = f"{account['account_name']} - {company}"
        
        # Check if account already exists
        if frappe.db.exists("Account", account_name):
            continue
        
        try:
            acc_doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": account["account_name"],
                "company": company,
                "parent_account": account["parent_account"],
                "is_group": account["is_group"],
                "root_type": account["root_type"],
                "report_type": account["report_type"],
                "account_type": account.get("account_type"),
                "account_currency": currency
            })
            acc_doc.insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Error creating account {account_name}: {str(e)}")


def setup_default_loan_accounts(company):
    """
    Set default loan accounts in company settings or Loan Product
    
    Args:
        company (str): Company name
    """
    
    # This function can be called to update existing Loan Products
    # with the newly created accounts
    
    loan_receivable = f"Loan Receivable - Microfinance - {company}"
    interest_income = f"Interest Income - Loans - {company}"
    interest_receivable = f"Interest Receivable - Microfinance - {company}"
    
    # Update all loan products for this company
    loan_products = frappe.get_all("Loan Product", 
        filters={"company": company},
        fields=["name"])
    
    for product in loan_products:
        doc = frappe.get_doc("Loan Product", product.name)
        if frappe.db.exists("Account", loan_receivable):
            doc.db_set("loan_receivable_account", loan_receivable, update_modified=False)
        if frappe.db.exists("Account", interest_income):
            doc.db_set("interest_income_account", interest_income, update_modified=False)
        if frappe.db.exists("Account", interest_receivable):
            doc.db_set("interest_receivable_account", interest_receivable, update_modified=False)
    
    frappe.msgprint(_(f"Updated {len(loan_products)} loan products with default accounts"))


@frappe.whitelist()
def create_accounts_for_company(company):
    """
    Manual function to create microfinance accounts for a specific company
    Can be called from console or custom button
    
    Args:
        company (str): Company name
    """
    if not frappe.db.exists("Company", company):
        frappe.throw(_("Company does not exist"))
    
    currency = frappe.db.get_value("Company", company, "default_currency")
    create_microfinance_accounts(company, currency)
    setup_default_loan_accounts(company)
    
    frappe.msgprint(_("Microfinance accounts created successfully"))
