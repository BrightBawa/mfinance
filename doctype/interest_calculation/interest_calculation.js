// Copyright (c) 2025, techypan@gmail.com and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Interest Calculation", {
// 	approved_amount(frm) {
//         calculate_interest_amount(frm)
// 	},
//     interest(frm) {
//         calculate_interest_amount(frm)
//     },
//     tenure(frm) {
//         calculate_interest_amount(frm)
//     },

//     setup(frm) 
//         frm.set_query("full_name", () => {
//             return {
//                 filters: {
//                     email: frm.doc.email
//             }
//         }
//     })
// });

frappe.ui.form.on("Interest Calculation", {
    approved_amount(frm) {
        calculate_interest_amount(frm); // Trigger calculation when approved_amount changes
    },
    interest(frm) {
        calculate_interest_amount(frm); // Trigger calculation when interest changes
    },
    tenure(frm) {
        calculate_interest_amount(frm); // Trigger calculation when tenure changes
    },
    setup(frm) {
        frm.set_query("full_name", () => {
            return {
                filters: {
                    email: frm.doc.email // Filter full_name based on the email field
                }
            };
        });
    }
});

// async function calculate_interest(frm){
//     frappe.call({
//         method: "loan_management.loan_management.doctype.interest_calculation.interest_calculation.calculate_interest",
//         args: { doc: JSON.stringify(frm.doc)
            
//         },
//        callback: function(result) {
//             if (result.message){
//                 frm.set_value({
//                     interest_amount: result.message.interest_amount, // Set the calculated interest amount
//                     final_amount: result.message.final_amount   
//                 })
//                 frappe.msgprint(`Interest calculated successfully. Final amount is ${r.message.final_amount} and interest amount is ${r.message.interest_amount}`);
//             }
//        },
//     });
// }

function calculate_interest_amount(frm){
    const interest_amount = flt(frm.doc.approved_amount) * flt(frm.doc.interest) * flt(frm.doc.tenure)/100
    frm.set_value("interest_amount", interest_amount)
    frm.set_value("final_amount", interest_amount + flt(frm.doc.approved_amount))

}