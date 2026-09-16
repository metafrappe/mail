"""Site regressions for the v16 port; no real mail server is contacted."""

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.model.base_document import get_controller
from frappe.modules.utils import get_module_app


def run(app: str = "mail") -> None:
	assert app == "mail"
	assert app in frappe.get_installed_apps()
	modules = frappe.get_all("Module Def", filters={"app_name": app}, pluck="name")
	assert set(modules) == {"Standalone Mail", "Client", "Server"}, modules
	doctypes = frappe.get_all("DocType", filters={"module": ["in", modules]}, pluck="name")
	assert doctypes
	for doctype in doctypes:
		frappe.get_meta(doctype)
		assert get_controller(doctype).__module__.startswith("mail."), doctype

	check_bootstrap()
	check_suite_exclusion()
	check_unconfigured_migrate()
	check_legacy_module_migration()
	print({"app": app, "controllers": len(doctypes), "regressions": "passed", "live_mail": "not tested"})


def check_bootstrap() -> None:
	assert frappe.db.exists("Role", "Mail Admin")
	assert frappe.db.exists("File", {"file_name": "Frappe Mail", "is_folder": 1})
	assert frappe.db.exists("Rate Limit", {"method_path": "mail.api.outbound.send"})
	settings = frappe.get_single("Mail Settings")
	assert settings.jmap_push_p256dh
	assert settings.get_password("jmap_push_private_key")
	assert settings.get_password("jmap_push_auth")
	settings.validate_jmap_push_subscription_keys()


def check_suite_exclusion() -> None:
	from mail.install import before_app_install, before_install

	with patch("frappe.get_installed_apps", return_value=["frappe", "suite"]):
		try:
			before_install()
		except frappe.ValidationError as error:
			assert "separate sites" in str(error)
		else:
			raise AssertionError("Standalone Mail must reject an existing Suite site")
	try:
		before_app_install("suite")
	except frappe.ValidationError as error:
		assert "separate sites" in str(error)
	else:
		raise AssertionError("Mail must reject installing Suite on the same site")
	before_app_install("erpnext")


def check_unconfigured_migrate() -> None:
	from mail import install

	with patch("mail.utils.get_config", return_value={}), patch.object(install, "StalwartCLI") as cli:
		install.after_migrate()
		cli.assert_not_called()
	credentials = {"server_url": "https://mail.example.invalid", "username": "test", "password": "test"}
	with (
		patch("mail.utils.get_config", return_value=credentials),
		patch.object(install, "StalwartCLI") as cli,
	):
		install.after_migrate()
		cli.return_value._install.assert_called_once()
		cli.return_value._install.side_effect = OSError("test download failure")
		try:
			install.after_migrate()
		except OSError:
			pass
		else:
			raise AssertionError("Configured Stalwart failures must remain visible")


def check_legacy_module_migration() -> None:
	"""Simulate legacy metadata on this disposable site and restore it via the patch."""
	from mail.patches.rename_standalone_mail_module import execute

	assert not frappe.db.exists("Module Def", "Mail")
	module_files = {
		app: Path(frappe.get_app_path(app, "modules.txt")).read_text()
		for app in ("mail", "suite")
		if app in frappe.get_all_apps()
	}
	for merge in (False, True):
		if merge:
			# A partially migrated site may already have both Module Def records.
			developer_mode = frappe.conf.developer_mode
			try:
				frappe.conf.developer_mode = 0
				frappe.get_doc({"doctype": "Module Def", "module_name": "Mail", "app_name": "mail"}).insert()
			finally:
				frappe.conf.developer_mode = developer_mode
		else:
			frappe.rename_doc(
				"Module Def",
				"Standalone Mail",
				"Mail",
				validate=False,
				rebuild_search=False,
				show_alert=False,
			)
		frappe.db.set_value("DocType", "Mail Settings", "module", "Mail", update_modified=False)
		frappe.db.set_value("DocType", "Rate Limit", "module", "Mail", update_modified=False)
		frappe.clear_cache()
		execute()
		execute()  # Re-running a completed migration must be harmless.
		assert not frappe.db.exists("Module Def", "Mail")
		assert frappe.db.get_value("Module Def", "Standalone Mail", "app_name") == "mail"
		assert frappe.db.get_value("DocType", "Mail Settings", "module") == "Standalone Mail"
		assert frappe.db.get_value("DocType", "Rate Limit", "module") == "Standalone Mail"
		assert get_controller("Mail Settings").__module__.startswith("mail.standalone_mail.")
	for app, content in module_files.items():
		assert Path(frappe.get_app_path(app, "modules.txt")).read_text() == content
	check_bootstrap()


def run_namespace_isolation(sites: tuple[str, ...] = ("test_mail", "test_suite")) -> None:
	"""Verify both sites in one process while both applications are on the bench."""
	for _ in range(2):
		for site in sites:
			frappe.init(site)
			try:
				frappe.connect()
				frappe.setup_module_map(include_all_apps=True)
				assert get_module_app("Standalone Mail") == "mail"
				assert get_module_app("Mail") == "suite"
				app = "suite" if "suite" in frappe.get_installed_apps() else "mail"
				expected_module = "Mail" if app == "suite" else "Standalone Mail"
				assert frappe.get_meta("Mail Settings").module == expected_module
				for doctype in ("Mail Settings", "User Account"):
					assert get_controller(doctype).__module__.startswith(app + "."), (site, doctype)
			finally:
				frappe.destroy()
	print({"sites": list(sites), "namespace_isolation": "passed"})
