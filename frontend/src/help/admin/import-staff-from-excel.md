---
title: Importing staff from Excel
summary: Onboard a whole laboratory from one Excel workbook, with groups, divisions and sections created for you, then print the activation slips.
audience: administrator
screen: none
updated: 2026-11-13
---

## What this is for

Use this to set up LabAdda for many people at once, for example when a laboratory first starts using it. One Excel workbook describes everyone: who they are, which group, division and section they belong to, and how they will first sign in. LabAdda reads it, shows a report of exactly what would be created, and only then saves everything. If any row has a problem, nothing at all is saved.

## Before you start

You need to be a site administrator, and whoever runs the server must have set the site's e-mail domain. Choose **Download the Excel template** on the import screen and fill it in. Save it as an Excel Workbook (.xlsx). A CSV file with the same column names also works. The file can be up to 1 MiB and 2,000 rows. Workbooks with macros (.xlsm) and password-protected workbooks are refused.

The columns are full_name, division, section, Emp No, email, Extension, Group, Residence Phone, username, Password, is_active and an optional role. Capital letters and spaces in the column names do not matter, so "Emp No" and "emp_no" are the same.

Required on every row: **full_name**, **Group**, **Emp No** and **username**. The **email** must be the username followed by the site's e-mail domain, for example `ananya.iyer@domain.in`. If you leave it blank it is filled in that way, and a different address is a problem on that row.

Division and section are optional, and nothing is ever filled in for you:

- With a division and a section, the person belongs to the section, inside the division, inside the group.
- With a division only, the person belongs to the division.
- With a section but no division, the section sits directly under the group and the person belongs to it.
- With neither, the person belongs directly to the group.

Other blank cells mean: Extension and Residence Phone stay empty, is_active means TRUE, role means member, and a blank Password means the person gets a printed activation slip.

## Steps

1. Open **Administration**, choose **People**, then choose **Import from Excel**.
2. Choose **Download the Excel template** if you need one, fill it in and save it.
3. Choose **Choose an Excel file** and pick your file. It is read at once and is not kept.
4. If the report shows **Rows with problems**, fix those rows in your spreadsheet and choose **Choose a different file**. Nothing has been saved.
5. Otherwise read the report: how many people will be added, which groups, divisions and sections will be created, and the full list of people. Units that do not exist yet appear under **What will happen** as steps starting "Create the". Existing units are matched by name, ignoring capital letters, inside the same parent. Two units with the same name under different parents are kept separate.
6. Anyone with admin in the role column is named in a red warning that they will become an administrator. Check it carefully: administrators can manage every person and unit.
7. Type the **Reason for this change**, then choose **Add** with the number of people.
8. If some people have no password in the file, their activation slips appear together. Choose **Print all activation slips** and hand each slip over privately.

## What happens next

Everything is saved together. Each new unit and each new person is recorded with your reason in the audit trail, and becoming an administrator is recorded too.

A person whose Password was filled in can sign in at once with that password, but must choose a new one before anything else. The password in your workbook is never shown again or written to the audit trail. A person with is_active set to FALSE is created with sign-in switched off and no slip; use **Reinstate** on their profile later. Email, extension and residence phone appear only on the person's own profile record and are visible only to people who can already open it.

## If something goes wrong

- "The first row has columns we do not use". Use the template's column names.
- "is required but this row leaves it blank". Fill in that cell on that row.
- "The email must be". Use the username at the site's e-mail domain, or leave email blank.
- "That username already has an account". The person already exists; remove the row.
- "The password is too short". Use at least 10 characters or leave the Password blank.
- "More than one unit under ... is called". Two existing units share a name there; rename one first.
- "That workbook contains macros" or "password-protected". Save a plain copy as .xlsx.
- "Something changed since you reviewed this file". Choose the file again to review a fresh report.
- The confirmation did not arrive. Reload the people list to see whether the people were added before trying again.

## Related

- [Importing a staff list](import-a-staff-list.md)
- [Adding a person](add-a-person.md)
- [The organisation chart](organisation-chart.md)
- [What the status words mean](status-words.md)
