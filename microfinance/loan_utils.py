"""
Core microfinance calculation and utility functions for bi_app
"""

from datetime import datetime, timedelta
import frappe


def calculate_repayment_schedule(
    loan_amount, tenure_months, annual_interest_rate, interest_method, frequency="Monthly"
):
    """
    Calculate repayment schedule based on interest calculation method.
    
    Args:
        loan_amount: Principal loan amount
        tenure_months: Loan tenure in months
        annual_interest_rate: Annual interest rate as percentage (e.g., 20 for 20%)
        interest_method: "Simple Interest", "Compound Interest Monthly", or "Declining Balance"
        frequency: "Monthly" or "Quarterly"
    
    Returns:
        dict with schedule entries, total_principal, total_interest, total_amount
    """
    schedule = []
    
    if frequency == "Quarterly":
        periods = tenure_months // 3
        period_days = 90
    else:  # Monthly
        periods = tenure_months
        period_days = 30
    
    if interest_method == "Simple Interest":
        schedule, total_interest = _calculate_simple_interest(
            loan_amount, periods, annual_interest_rate, period_days, frequency
        )
    elif interest_method == "Compound Interest Monthly":
        schedule, total_interest = _calculate_compound_interest(
            loan_amount, periods, annual_interest_rate, period_days, frequency
        )
    else:  # Declining Balance
        schedule, total_interest = _calculate_declining_balance(
            loan_amount, periods, annual_interest_rate, period_days, frequency
        )
    
    total_amount = loan_amount + total_interest
    
    return {
        "schedule_entries": schedule,
        "total_principal": loan_amount,
        "total_interest": total_interest,
        "total_amount": total_amount,
    }


def _calculate_simple_interest(principal, periods, annual_rate, period_days, frequency):
    """Calculate Simple Interest repayment schedule"""
    schedule = []
    period_rate = (annual_rate / 100 / 365) * period_days
    per_period_principal = principal / periods
    per_period_interest = principal * period_rate
    total_interest = per_period_interest * periods
    
    start_date = datetime.now()
    for i in range(1, periods + 1):
        if frequency == "Quarterly":
            due_date = start_date + timedelta(days=90 * i)
        else:
            due_date = start_date + timedelta(days=30 * i)
        
        schedule.append({
            "due_date": due_date.date(),
            "principal_amount": per_period_principal,
            "interest_amount": per_period_interest,
            "total_amount": per_period_principal + per_period_interest,
            "status": "Not Due",
            "payment_reference": None,
        })
    
    return schedule, total_interest


def _calculate_compound_interest(principal, periods, annual_rate, period_days, frequency):
    """Calculate Compound Interest (Monthly) repayment schedule"""
    schedule = []
    monthly_rate = annual_rate / 12 / 100
    per_period_principal = principal / periods
    total_interest = 0
    
    start_date = datetime.now()
    outstanding = principal
    
    for i in range(1, periods + 1):
        per_period_interest = outstanding * monthly_rate
        total_interest += per_period_interest
        outstanding -= per_period_principal
        
        if frequency == "Quarterly":
            due_date = start_date + timedelta(days=90 * i)
        else:
            due_date = start_date + timedelta(days=30 * i)
        
        schedule.append({
            "due_date": due_date.date(),
            "principal_amount": per_period_principal,
            "interest_amount": per_period_interest,
            "total_amount": per_period_principal + per_period_interest,
            "status": "Not Due",
            "payment_reference": None,
        })
    
    return schedule, total_interest


def _calculate_declining_balance(principal, periods, annual_rate, period_days, frequency):
    """Calculate Declining Balance repayment schedule"""
    schedule = []
    monthly_rate = annual_rate / 12 / 100
    per_period_principal = principal / periods
    total_interest = 0
    
    start_date = datetime.now()
    outstanding = principal
    
    for i in range(1, periods + 1):
        per_period_interest = outstanding * monthly_rate
        total_interest += per_period_interest
        outstanding -= per_period_principal
        
        if frequency == "Quarterly":
            due_date = start_date + timedelta(days=90 * i)
        else:
            due_date = start_date + timedelta(days=30 * i)
        
        schedule.append({
            "due_date": due_date.date(),
            "principal_amount": per_period_principal,
            "interest_amount": per_period_interest,
            "total_amount": per_period_principal + per_period_interest,
            "status": "Not Due",
            "payment_reference": None,
        })
    
    return schedule, total_interest


@frappe.whitelist()
def verify_government_worker_affordability(government_id, api_endpoint, api_key, loan_id):
    """
    Poll GOGTPRS API for government worker affordability assessment.
    
    Args:
        government_id: Government ID number
        api_endpoint: GOGTPRS API endpoint URL
        api_key: API key for authentication
        loan_id: Loan document ID
    
    Returns:
        dict with verification status and affordability data or None if failed
    """
    import requests
    
    loan = frappe.get_doc("Loan", loan_id)
    
    try:
        response = requests.post(
            f"{api_endpoint}/verify",
            json={"government_id": government_id},
            headers={"Authorization": f"Bearer {api_key}", "X-API-Key": api_key},
            timeout=30,
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "Verified",
                "monthly_income": data.get("monthly_income"),
                "existing_obligations": data.get("existing_obligations"),
                "recommended_max_loan": data.get("recommended_max_loan"),
                "verification_date": datetime.now(),
            }
        else:
            # API failed, flag for manual review
            handle_verification_failure(
                loan_id, f"GOGTPRS API returned status code {response.status_code}"
            )
            return None
    except requests.exceptions.Timeout:
        handle_verification_failure(loan_id, "GOGTPRS API verification timed out")
        return None
    except Exception as e:
        handle_verification_failure(loan_id, f"GOGTPRS API verification failed: {str(e)}")
        return None


def handle_verification_failure(loan_id, error_message):
    """
    Flag loan for manual review when government verification fails.
    
    Args:
        loan_id: Loan document ID
        error_message: Error message describing the failure
    """
    loan = frappe.get_doc("Loan", loan_id)
    loan.government_verification_status = "Manual Review"
    loan.government_verification_flag_date = datetime.now()
    loan.government_verification_notes = error_message
    loan.save()
    
    # Send notification to Branch Manager
    frappe.sendmail(
        recipients=[loan.approval_officer],
        subject=f"Manual Review Required: Loan {loan_id}",
        message=f"""
        Loan {loan_id} requires manual verification review.
        
        Borrower: {loan.borrower}
        Reason: {error_message}
        
        Please review and approve manually if appropriate.
        """,
    )


@frappe.whitelist()
def approve_manually_verified(loan_id, reviewer_notes):
    """
    Approve a loan after manual verification review.
    
    Args:
        loan_id: Loan document ID
        reviewer_notes: Notes from the reviewer
    """
    loan = frappe.get_doc("Loan", loan_id)
    loan.government_verification_status = "Verified"
    loan.manual_verified_by = frappe.session.user
    loan.manual_verified_date = datetime.now()
    loan.manual_verification_notes = reviewer_notes
    loan.save()
    
    frappe.msgprint(f"Loan {loan_id} manually verified successfully")
