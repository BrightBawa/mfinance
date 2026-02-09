app_name = "bi_app"
app_title = "Bestinvest App"
app_publisher = "Bright Bawa"
app_description = "Comprehensive microfinance platform with multi-branch support, flexible interest calculations (Simple/Compound/Declining Balance), GOGTPRS integration for government worker verification, multi-currency support, and complete loan lifecycle management"
app_email = "brightbawa11@gmail.com"
app_license = "mit"
app_version = "0.1.0"

add_to_apps_screen = [
    {
        "name": "bi_app",
        "logo": "/assets/bi_app/logo.png",
        "title": "Bestinvest App",
        "route": "/app/loan",
        "has_permission": "bi_app.microfinance.permissions.has_app_permission"
    }
]

# DocType JS
doctype_js = {
    "Loan": "public/js/loan.js",
    "Payment": "public/js/payment.js",
}

# Fixtures - Pre-configured loan products, number cards, dashboard charts, workflow, email alerts, print formats, and workspace
fixtures = [
    {
        "doctype": "Workflow State"
    },
    {
        "doctype": "Workflow",
        "filters": [["document_type", "=", "Loan"]]
    },
    {
        "doctype": "Loan Product",
        "filters": [["name", "in", [
            "Personal Loan",
            "Agricultural Loan",
            "Emergency Loan",
            "Housing Loan",
            "Education Loan",
            "Government Worker Special"
        ]]]
    },
    {
        "doctype": "Number Card",
        "filters": [["name", "in", [
            "Total Loans",
            "Active Loans",
            "Pending Approvals",
            "Repayment Collection Rate",
            "Total Borrowers",
            "Government Workers",
            "Document Verification Rate",
            "Late Payment Rate",
            "Total Branches",
            "Total Loan Products",
            "Total Collateral Value",
            "Total Co-Signers",
            "Total Loan Applications",
            "Pending Loan Approvals",
            "Approved Loan Applications"
        ]]]
    },
    {
        "doctype": "Dashboard Chart",
        "filters": [["name", "in", [
            "Loan Status Distribution",
            "Approval Trends",
            "Payment Performance",
            "Borrower Demographics",
            "Verification Status",
            "Collection Trend",
            "Loan Application Status",
            "Loan Approval Workflow"
        ]]]
    }
]

# After Install Hook
after_install = "bi_app.setup.install.after_install"
