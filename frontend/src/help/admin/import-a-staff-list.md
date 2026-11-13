---
title: Importing a staff list
summary: Add or update many people at once from a spreadsheet saved as CSV, check a report first, and print all the activation slips together.
audience: administrator
screen: none
updated: 2026-11-13
---

## What this is for

Use this when several people join at once, or when a spreadsheet from the personnel office needs to be brought into LabAdda. You upload the file, read a report of exactly what would happen, choose the rows you want, and apply them together. People who are not in the file are never changed.

## Before you start

You need to be a site administrator. Save your spreadsheet as **CSV UTF-8**. The file can be up to 1 MiB and 2,000 rows. The first line names the columns: employee_no, username, display_name, designation, unit_code, role, status and effective_on. Only username is required. Choose **Download the template** on the import screen to see an example row. The unit_code is the short code shown beside each unit on the Organisation chart.

## Steps

1. Open **Administration**, choose **People**, then choose **Import staff list**.
2. Choose **Download the template** if you need one, fill it in and save it as CSV.
3. Choose **Choose a CSV file** and pick your file. It is read at once and is not kept.
4. Read the **Import report**. Rows are grouped as new people to add, people who move to another unit, people whose details change, and rows with problems. Each row shows what will happen in plain words and any things to check.
5. Rows with problems cannot be applied. Fix them in your spreadsheet and choose **Choose a different file**, or leave them out. Untick any row you do not want, or use **Select all** for a group.
6. Choose **Review** and read **What will happen** and **Things to check**.
7. Type the **Reason for this change**, then choose **Apply**.
8. The activation slips for all new people appear together. Choose **Print all activation slips**.

## What happens next

All the chosen rows are applied together: either every change is made or none is. Blank cells leave the stored value alone. A new person is created as Invited with their home unit and role. A different unit_code moves an existing person. Putting suspended in the status column suspends them. Leave, retirement and departure are done from the person's profile. Text that begins with =, +, - or @ is saved as plain text and is never calculated. People in the system but missing from the file are listed for information and are not changed. Each change is recorded with your reason on the person's **Timeline**.

To move or suspend several people already in LabAdda, tick them in the people list (up to 100), choose **Move to unit** and **Review move**, or choose **Review suspension**. They go through the same review and reason.

## If something goes wrong

- "The file is not UTF-8 text". In your spreadsheet choose Save As, then CSV UTF-8.
- "That file is too large". Split it into files of up to 2,000 rows.
- "The first line has columns we do not use". Use the template's column names.
- "No open unit has the code". Check the code on the Organisation chart.
- "Someone changed this record or its consequences". A fresh plan is shown; read it again and apply.
- The confirmation did not arrive. Reload the people list to see whether the people were added before trying again.
- Activation codes are shown only once. If a slip was lost, open the person's profile and issue a new code.

## Related

- [Importing staff from Excel](import-staff-from-excel.md)
- [Adding a person](add-a-person.md)
- [Transferring a person](transfer.md)
- [What the status words mean](status-words.md)
