"""Move standalone Mail's module without taking ownership of Suite's Mail module."""

import frappe


def execute() -> None:
	from mail.install import before_install

	before_install()
	old_module = frappe.db.get_value("Module Def", "Mail", ["name", "app_name"], as_dict=True)
	if not old_module:
		return
	if old_module.app_name != "mail":
		frappe.throw(frappe._("Cannot migrate the Mail module because it belongs to another app."))

	target_module = frappe.db.get_value("Module Def", "Standalone Mail", ["name", "app_name"], as_dict=True)
	if target_module and target_module.app_name != "mail":
		frappe.throw(frappe._("The Standalone Mail module belongs to another app."))

	# Standard Module Def records reject interactive renames. Ownership is checked
	# above; Frappe's rename machinery updates every Module Def link, including
	# DocTypes, Custom Fields and Workspaces, without rewriting mail records.
	# Module Def's developer-mode delete hook edits source directories. A merge
	# must only change site metadata, even on a developer site sharing this bench.
	developer_mode = frappe.conf.developer_mode
	try:
		frappe.conf.developer_mode = 0
		frappe.rename_doc(
			"Module Def",
			"Mail",
			"Standalone Mail",
			merge=bool(target_module),
			ignore_permissions=True,
			validate=False,
			rebuild_search=False,
			show_alert=False,
		)
	finally:
		frappe.conf.developer_mode = developer_mode
	frappe.clear_cache()
